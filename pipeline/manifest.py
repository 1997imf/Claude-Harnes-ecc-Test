"""The manifest records what each stage did, so runs can be resumed safely.

Manifests are immutable pydantic models: updates return a new copy that is
then written to disk atomically (write temp file, then rename).
"""

import hashlib
import json
import os
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from pipeline import __version__

MISSING_FILE_HASH = "missing"
HASH_CHUNK_BYTES = 1 << 20

StageStatus = Literal["pending", "running", "completed", "failed"]


class ManifestError(RuntimeError):
    """The manifest file exists but cannot be read."""


class StageRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: StageStatus = "pending"
    input_hash: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    artifacts: tuple[str, ...] = ()
    error: str | None = None


class Manifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    pipeline_version: str
    brief_path: str
    brief: dict[str, Any] | None = None
    brief_sha256: str | None = None
    stages: dict[str, StageRecord]
    updated_at: str


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def file_sha256(path: Path) -> str:
    if not path.is_file():
        return MISSING_FILE_HASH
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def fingerprint(stage_name: str, input_paths: Iterable[Path]) -> str:
    """Hash of the stage name, pipeline version, and every input file's content."""
    digest = hashlib.sha256(f"{stage_name}|{__version__}".encode())
    for path in input_paths:
        digest.update(f"|{path.name}:{file_sha256(path)}".encode())
    return digest.hexdigest()


def new_manifest(stage_names: Iterable[str], brief_path: Path) -> Manifest:
    return Manifest(
        pipeline_version=__version__,
        brief_path=str(brief_path),
        stages={name: StageRecord() for name in stage_names},
        updated_at=now_iso(),
    )


def with_stage(manifest: Manifest, name: str, record: StageRecord) -> Manifest:
    if name not in manifest.stages:
        raise KeyError(f"Unknown stage {name!r}")
    stages = {**manifest.stages, name: record}
    return manifest.model_copy(update={"stages": stages, "updated_at": now_iso()})


def load_manifest(path: Path) -> Manifest | None:
    if not path.is_file():
        return None
    try:
        return Manifest.model_validate_json(path.read_text(encoding="utf-8"))
    except (ValidationError, ValueError) as error:
        raise ManifestError(
            f"{path} is corrupt or from an incompatible version. "
            f"Delete it to start fresh. Details: {error}"
        ) from error


def save_manifest(path: Path, manifest: Manifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(manifest.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)
