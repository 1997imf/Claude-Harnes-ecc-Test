"""Tests for the render stage: command building, environment, failure handling."""

import subprocess
import sys

import pytest

from pipeline.runner import StageError
from pipeline.schemas import SceneParams
from pipeline.stages import render
from pipeline.stages.plan import run as plan_run
from pipeline.visuals import VISUALS
from tests.conftest import write_brief


def test_render_command_is_an_argument_list_at_low_quality(tmp_path):
    command = render.build_render_command(tmp_path / "scene.py", "MyScene", tmp_path / "media", (480, 854))

    assert command[:4] == [sys.executable, "-m", "manim", "render"]
    assert command[command.index("--quality") + 1] == "l"
    assert "--disable_caching" in command
    assert command[command.index("--resolution") + 1] == "480,854"
    assert command[-1] == "MyScene"


def test_render_environment_drops_secrets_and_points_at_scene_files(example_project):
    base = {"PATH": "/bin", "ANTHROPIC_API_KEY": "sk-x", "GH_TOKEN": "t", "DB_PASSWORD": "p"}

    env = render.render_environment(base, example_project)

    assert env["PATH"] == "/bin"
    assert not {"ANTHROPIC_API_KEY", "GH_TOKEN", "DB_PASSWORD"} & env.keys()
    assert env[render.PARAMS_ENV] == str(example_project.scene_params)
    assert env[render.FACTS_ENV] == str(example_project.render_facts)


def _prepare(project):
    plan_run(project)


def test_scene_params_wrap_storyboard_and_pin_template_hash(example_project):
    _prepare(example_project)

    render.write_scene_params(example_project)

    params = SceneParams.model_validate_json(example_project.scene_params.read_text())
    assert params.scene_class == VISUALS["secant_tangent"].scene_class
    assert params.storyboard.x0 == 1.0
    assert len(params.template_sha256) == 64


def test_nonzero_exit_raises_stage_error_and_writes_log(example_project, monkeypatch):
    _prepare(example_project)
    fake = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="Boom: bad scene\n")
    monkeypatch.setattr(render.subprocess, "run", lambda *a, **k: fake)

    with pytest.raises(StageError, match="exit code 1") as error:
        render.run(example_project)

    assert "Boom: bad scene" in str(error.value)
    assert "Boom: bad scene" in example_project.render_log.read_text()


def test_timeout_raises_stage_error(example_project, monkeypatch):
    _prepare(example_project)

    def too_slow(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="manim", timeout=1)

    monkeypatch.setattr(render.subprocess, "run", too_slow)

    with pytest.raises(StageError, match="timed out"):
        render.run(example_project)


def test_success_without_video_raises_stage_error(example_project, monkeypatch):
    _prepare(example_project)
    fake = subprocess.CompletedProcess(args=[], returncode=0, stdout="ok", stderr="")
    monkeypatch.setattr(render.subprocess, "run", lambda *a, **k: fake)

    with pytest.raises(StageError, match="no MP4"):
        render.run(example_project)


def test_stale_video_is_removed_before_rendering(example_project, monkeypatch):
    _prepare(example_project)
    example_project.video.parent.mkdir(parents=True, exist_ok=True)
    example_project.video.write_bytes(b"old video")
    fake = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="fail")
    monkeypatch.setattr(render.subprocess, "run", lambda *a, **k: fake)

    with pytest.raises(StageError):
        render.run(example_project)

    assert not example_project.video.exists()


@pytest.mark.integration
def test_real_manim_failure_is_reported(example_project, tmp_path, monkeypatch):
    _prepare(example_project)
    broken = tmp_path / "broken_scene.py"
    broken.write_text(
        "from manim import Scene\n"
        f"class {VISUALS['secant_tangent'].scene_class}(Scene):\n"
        "    def construct(self):\n"
        "        raise RuntimeError('template exploded')\n"
    )
    monkeypatch.setitem(VISUALS, "secant_tangent", VISUALS["secant_tangent"]._replace(template_file=broken))

    with pytest.raises(StageError, match="exit code") as error:
        render.run(example_project)

    assert "render.log" in str(error.value)
    assert "template exploded" in example_project.render_log.read_text()


@pytest.mark.parametrize(
    "brief, scene_class",
    [
        ({"template": "pythagoras", "topic": "t", "a": 3, "b": 4}, "PythagorasTemplate"),
        ({"template": "odd_sum", "topic": "t", "n": 4, "format": "portrait"}, "OddSumTemplate"),
    ],
)
def test_each_visual_type_is_routed_to_its_own_template(tmp_path, brief, scene_class):
    project = write_brief(tmp_path / "p", brief)
    plan_run(project)

    params = render.write_scene_params(project)

    assert params.scene_class == scene_class
    assert params.template_file == str(VISUALS[brief["template"]].template_file)
