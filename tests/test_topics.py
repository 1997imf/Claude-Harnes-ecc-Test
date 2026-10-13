"""Tests for automatic topic selection."""

import json

import pytest

from pipeline.manifest import StageRecord, new_manifest, save_manifest, with_stage
from pipeline.schemas import Brief
from pipeline.stages.plan import build_storyboard, verify_storyboard
from pipeline.topics import CATALOG, project_slug, select_topic, write_topic_brief


def _mark_produced(projects_dir, topic, finished_at, video_format="portrait"):
    project = projects_dir / project_slug(topic, video_format)
    manifest = new_manifest(["package"], project / "brief.json")
    record = StageRecord(status="completed", finished_at=finished_at)
    save_manifest(project / "manifest.json", with_stage(manifest, "package", record))


def test_first_selection_is_first_catalog_topic(tmp_path):
    assert select_topic(tmp_path, "portrait") == CATALOG[0]


def test_produced_topics_are_not_selected_again(tmp_path):
    _mark_produced(tmp_path, CATALOG[0], "2026-10-13T10:00:00+00:00")

    assert select_topic(tmp_path, "portrait") == CATALOG[1]


def test_when_all_produced_the_least_recent_is_chosen(tmp_path):
    for index, topic in enumerate(CATALOG):
        _mark_produced(tmp_path, topic, f"2026-10-13T1{index}:00:00+00:00")
    _mark_produced(tmp_path, CATALOG[0], "2026-10-13T23:00:00+00:00")

    assert select_topic(tmp_path, "portrait") == CATALOG[1]


def test_formats_are_tracked_separately(tmp_path):
    _mark_produced(tmp_path, CATALOG[0], "2026-10-13T10:00:00+00:00", "landscape")

    assert select_topic(tmp_path, "portrait") == CATALOG[0]


def test_explicit_topic_and_unknown_topic(tmp_path):
    assert select_topic(tmp_path, "portrait", CATALOG[2].id) == CATALOG[2]
    with pytest.raises(ValueError, match="Unknown topic"):
        select_topic(tmp_path, "portrait", "nope")


def test_written_brief_is_valid(tmp_path):
    path = write_topic_brief(CATALOG[1], "portrait", tmp_path)

    brief = Brief.model_validate(json.loads(path.read_text()))
    assert brief.function == CATALOG[1].function and brief.format == "portrait"


@pytest.mark.parametrize("topic", CATALOG, ids=lambda t: t.id)
def test_every_catalog_topic_passes_the_pre_render_math_check(topic, tmp_path):
    brief = Brief.model_validate(json.loads(write_topic_brief(topic, "portrait", tmp_path).read_text()))

    verify_storyboard(build_storyboard(brief))  # raises StageError on any wrong claim
