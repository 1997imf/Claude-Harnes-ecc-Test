"""Runs stages in order, skipping those whose inputs and outputs are unchanged.

A stage is "fresh" (skipped) only if the manifest says it completed, the
fingerprint of its inputs still matches, and every output exists, is
non-empty, and passes the stage's own validation.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from pipeline.manifest import (
    Manifest,
    StageRecord,
    fingerprint,
    load_manifest,
    new_manifest,
    now_iso,
    save_manifest,
    with_stage,
)
from pipeline.paths import ProjectPaths

Log = Callable[[str], None]


class StageError(RuntimeError):
    """A stage failed for a reason the user can act on."""


class Stage(NamedTuple):
    name: str
    inputs: Callable[[ProjectPaths], tuple[Path, ...]]
    outputs: Callable[[ProjectPaths], tuple[Path, ...]]
    run: Callable[[ProjectPaths], None]
    # Optional deeper check of outputs (e.g. JSON parses); raises StageError.
    validate: Callable[[ProjectPaths], None] | None = None


@dataclass(frozen=True)
class PipelineResult:
    succeeded: bool
    ran: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()
    failed_stage: str | None = None
    error: str | None = None


def check_outputs(stage: Stage, paths: ProjectPaths) -> None:
    for output in stage.outputs(paths):
        if not output.is_file() or output.stat().st_size == 0:
            raise StageError(f"{stage.name} did not produce {paths.relative(output)}")
    if stage.validate is not None:
        stage.validate(paths)


def _is_fresh(stage: Stage, record: StageRecord, input_hash: str, paths: ProjectPaths) -> bool:
    if record.status != "completed" or record.input_hash != input_hash:
        return False
    try:
        check_outputs(stage, paths)
    except StageError:
        return False
    return True


def _read_brief_snapshot(paths: ProjectPaths) -> dict | None:
    try:
        data = json.loads(paths.brief.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _start_manifest(paths: ProjectPaths, stages: tuple[Stage, ...]) -> Manifest:
    names = [stage.name for stage in stages]
    existing = load_manifest(paths.manifest)
    if existing is None or list(existing.stages) != names:
        existing = new_manifest(names, paths.brief)
    return existing.model_copy(
        update={
            "brief": _read_brief_snapshot(paths),
            "brief_sha256": fingerprint("brief", [paths.brief]),
        }
    )


def _reset_downstream(manifest: Manifest, stages: tuple[Stage, ...], index: int) -> Manifest:
    for later in stages[index + 1 :]:
        manifest = with_stage(manifest, later.name, StageRecord())
    return manifest


def _run_one(stage: Stage, paths: ProjectPaths) -> str | None:
    """Run a stage and verify its outputs. Returns an error message or None."""
    try:
        stage.run(paths)
        check_outputs(stage, paths)
    except StageError as error:
        return str(error)
    except Exception as error:  # noqa: BLE001 - recorded in the manifest, not swallowed
        return f"{type(error).__name__}: {error}"
    return None


def run_pipeline(
    paths: ProjectPaths,
    stages: tuple[Stage, ...],
    *,
    force: bool = False,
    log: Log = print,
) -> PipelineResult:
    paths.project_dir.mkdir(parents=True, exist_ok=True)
    manifest = _start_manifest(paths, stages)
    save_manifest(paths.manifest, manifest)
    ran: list[str] = []
    skipped: list[str] = []

    for index, stage in enumerate(stages):
        input_hash = fingerprint(stage.name, stage.inputs(paths))
        if not force and _is_fresh(stage, manifest.stages[stage.name], input_hash, paths):
            log(f"✓ {stage.name}: up to date (skipped)")
            skipped.append(stage.name)
            continue

        log(f"→ {stage.name}: running…")
        started = now_iso()
        manifest = with_stage(manifest, stage.name, StageRecord(status="running", started_at=started))
        save_manifest(paths.manifest, manifest)

        error = _run_one(stage, paths)
        if error is not None:
            failed = StageRecord(
                status="failed", input_hash=input_hash, started_at=started,
                finished_at=now_iso(), error=error,
            )
            manifest = _reset_downstream(with_stage(manifest, stage.name, failed), stages, index)
            save_manifest(paths.manifest, manifest)
            log(f"✗ {stage.name}: failed")
            return PipelineResult(False, tuple(ran), tuple(skipped), stage.name, error)

        done = StageRecord(
            status="completed", input_hash=input_hash, started_at=started, finished_at=now_iso(),
            artifacts=tuple(paths.relative(p) for p in stage.outputs(paths)),
        )
        manifest = with_stage(manifest, stage.name, done)
        save_manifest(paths.manifest, manifest)
        log(f"✓ {stage.name}: completed")
        ran.append(stage.name)

    return PipelineResult(True, tuple(ran), tuple(skipped))


def describe_stages(
    paths: ProjectPaths, stages: tuple[Stage, ...]
) -> list[tuple[str, str, str | None]]:
    """(stage, state, error) for `status`. Completed stages whose inputs changed are 'outdated'."""
    manifest = load_manifest(paths.manifest)
    rows = []
    for stage in stages:
        record = manifest.stages.get(stage.name, StageRecord()) if manifest else StageRecord()
        state = record.status
        if state == "completed":
            input_hash = fingerprint(stage.name, stage.inputs(paths))
            if not _is_fresh(stage, record, input_hash, paths):
                state = "outdated"
        rows.append((stage.name, state, record.error))
    return rows
