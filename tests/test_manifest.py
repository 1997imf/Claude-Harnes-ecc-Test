"""Tests for the manifest file: creation, persistence, hashing."""

import json

import pytest

from pipeline import __version__
from pipeline.manifest import (
    ManifestError,
    StageRecord,
    file_sha256,
    fingerprint,
    load_manifest,
    new_manifest,
    save_manifest,
    with_stage,
)

STAGES = ("plan", "render")


def test_new_manifest_marks_every_stage_pending(tmp_path):
    manifest = new_manifest(STAGES, tmp_path / "brief.json")

    assert manifest.pipeline_version == __version__
    assert list(manifest.stages) == list(STAGES)
    assert all(record.status == "pending" for record in manifest.stages.values())


def test_save_and_load_round_trip(tmp_path):
    path = tmp_path / "manifest.json"
    manifest = new_manifest(STAGES, tmp_path / "brief.json")

    save_manifest(path, manifest)

    assert load_manifest(path) == manifest
    assert not list(tmp_path.glob("*.tmp")), "atomic write must not leave temp files"


def test_load_manifest_returns_none_when_missing(tmp_path):
    assert load_manifest(tmp_path / "manifest.json") is None


@pytest.mark.parametrize("content", ["{not json", json.dumps({"stages": "wrong"})])
def test_load_manifest_rejects_corrupt_file(tmp_path, content):
    path = tmp_path / "manifest.json"
    path.write_text(content)

    with pytest.raises(ManifestError, match="manifest.json"):
        load_manifest(path)


def test_with_stage_returns_new_manifest_without_mutating_original(tmp_path):
    original = new_manifest(STAGES, tmp_path / "brief.json")
    record = StageRecord(status="completed", input_hash="abc", artifacts=("x.json",))

    updated = with_stage(original, "plan", record)

    assert updated.stages["plan"] == record
    assert original.stages["plan"].status == "pending"


def test_with_stage_rejects_unknown_stage(tmp_path):
    with pytest.raises(KeyError):
        with_stage(new_manifest(STAGES, tmp_path / "b.json"), "upload", StageRecord())


def test_file_sha256_changes_with_content_and_marks_missing_files(tmp_path):
    path = tmp_path / "a.txt"
    path.write_text("one")
    first = file_sha256(path)
    path.write_text("two")

    assert file_sha256(path) != first
    assert file_sha256(tmp_path / "missing.txt") == "missing"


def test_fingerprint_depends_on_stage_name_and_inputs(tmp_path):
    path = tmp_path / "a.txt"
    path.write_text("one")

    base = fingerprint("plan", [path])
    assert fingerprint("plan", [path]) == base
    assert fingerprint("render", [path]) != base
    path.write_text("two")
    assert fingerprint("plan", [path]) != base
