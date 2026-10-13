"""Tests for stage orchestration: skipping fresh stages, invalidation, failures.

Uses small fake stages so no video is rendered.
"""

import json

import pytest

from pipeline.manifest import load_manifest
from pipeline.paths import ProjectPaths
from pipeline.runner import Stage, StageError, describe_stages, run_pipeline


class FakeStages:
    """Two chained stages: a copies the brief, b copies a's output."""

    def __init__(self):
        self.calls = []
        self.fail_b = False

    def _run_a(self, paths):
        self.calls.append("a")
        (paths.project_dir / "a.txt").write_text(paths.brief.read_text())

    def _run_b(self, paths):
        self.calls.append("b")
        if self.fail_b:
            raise StageError("b exploded")
        (paths.project_dir / "b.txt").write_text((paths.project_dir / "a.txt").read_text())

    def stages(self):
        return (
            Stage(
                name="a",
                inputs=lambda p: (p.brief,),
                outputs=lambda p: (p.project_dir / "a.txt",),
                run=self._run_a,
            ),
            Stage(
                name="b",
                inputs=lambda p: (p.project_dir / "a.txt",),
                outputs=lambda p: (p.project_dir / "b.txt",),
                run=self._run_b,
            ),
        )


@pytest.fixture
def project(tmp_path):
    brief = tmp_path / "proj" / "brief.json"
    brief.parent.mkdir()
    brief.write_text(json.dumps({"v": 1}))
    return ProjectPaths.from_brief(brief)


def _run(project, fake, **kwargs):
    return run_pipeline(project, stages=fake.stages(), log=lambda _msg: None, **kwargs)


def test_first_run_executes_all_stages_and_records_them(project):
    fake = FakeStages()

    result = _run(project, fake)

    assert result.succeeded and result.ran == ("a", "b")
    manifest = load_manifest(project.manifest)
    assert manifest.stages["b"].status == "completed"
    assert manifest.stages["b"].artifacts == ("b.txt",)
    assert manifest.brief == {"v": 1}
    assert manifest.stages["a"].finished_at is not None


def test_second_run_skips_fresh_stages(project):
    fake = FakeStages()
    _run(project, fake)

    result = _run(project, fake)

    assert result.skipped == ("a", "b") and result.ran == ()
    assert fake.calls == ["a", "b"]


def test_changed_brief_reruns_downstream_stages(project):
    fake = FakeStages()
    _run(project, fake)
    project.brief.write_text(json.dumps({"v": 2}))

    result = _run(project, fake)

    assert result.ran == ("a", "b")


def test_deleted_artifact_triggers_rerun_of_that_stage(project):
    fake = FakeStages()
    _run(project, fake)
    (project.project_dir / "b.txt").unlink()

    result = _run(project, fake)

    assert result.skipped == ("a",) and result.ran == ("b",)


def test_empty_artifact_is_not_considered_complete(project):
    fake = FakeStages()
    _run(project, fake)
    (project.project_dir / "b.txt").write_text("")

    assert _run(project, fake).ran == ("b",)


def test_force_reruns_everything(project):
    fake = FakeStages()
    _run(project, fake)

    assert _run(project, fake, force=True).ran == ("a", "b")


def test_failed_stage_is_recorded_and_stops_the_pipeline(project):
    fake = FakeStages()
    fake.fail_b = True

    result = _run(project, fake)

    assert not result.succeeded
    assert result.failed_stage == "b" and "b exploded" in result.error
    record = load_manifest(project.manifest).stages["b"]
    assert record.status == "failed" and record.error == "b exploded"


def test_stage_that_does_not_write_its_output_fails(project):
    fake = FakeStages()
    stages = (fake.stages()[0]._replace(run=lambda p: None),)

    result = run_pipeline(project, stages=stages, log=lambda _m: None)

    assert not result.succeeded and "did not produce" in result.error


def test_unexpected_exception_is_recorded_with_its_type(project):
    def boom(_paths):
        raise RuntimeError("disk on fire")

    stages = (FakeStages().stages()[0]._replace(run=boom),)

    result = run_pipeline(project, stages=stages, log=lambda _m: None)

    assert result.error == "RuntimeError: disk on fire"


def test_resume_after_failure_reruns_only_failed_stage(project):
    fake = FakeStages()
    fake.fail_b = True
    _run(project, fake)
    fake.fail_b = False

    result = _run(project, fake)

    assert result.skipped == ("a",) and result.ran == ("b",)


def test_failure_upstream_resets_downstream_to_pending(project):
    fake = FakeStages()
    _run(project, fake)
    stages = (fake.stages()[0]._replace(run=lambda p: (_ for _ in ()).throw(StageError("x"))),
              fake.stages()[1])
    project.brief.write_text(json.dumps({"v": 3}))

    run_pipeline(project, stages=stages, log=lambda _m: None)

    assert load_manifest(project.manifest).stages["b"].status == "pending"


def test_describe_stages_reports_completed_failed_and_outdated(project):
    fake = FakeStages()
    fake.fail_b = True
    _run(project, fake)
    assert describe_stages(project, fake.stages()) == [
        ("a", "completed", None),
        ("b", "failed", "b exploded"),
    ]

    project.brief.write_text(json.dumps({"v": 9}))
    assert describe_stages(project, fake.stages())[0][1] == "outdated"


def test_progress_messages_are_logged(project):
    messages = []

    run_pipeline(project, stages=FakeStages().stages(), log=messages.append)
    run_pipeline(project, stages=FakeStages().stages(), log=messages.append)

    assert any("a: running" in m for m in messages)
    assert any("a: up to date" in m for m in messages)
