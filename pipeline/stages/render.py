"""Render stage: storyboard.json -> scene/scene.json -> renders/secant_tangent.mp4 (480p).

No Python code is generated: the stage writes parameters for a fixed, reviewed
Manim template. Manim runs in a separate process with an argument list (never
a shell), a timeout, and an environment with secret-looking variables removed.
"""

import os
import shutil
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

from pipeline.manifest import file_sha256
from pipeline.paths import VIDEO_FILENAME, ProjectPaths
from pipeline.runner import StageError
from pipeline.schemas import RenderFacts, SceneParams, Storyboard
from pipeline.stages._io import read_model, write_model

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_FILE = REPO_ROOT / "pipeline" / "templates" / "secant_tangent_scene.py"
SCENE_CLASS = "SecantTangentTemplate"
RENDER_TIMEOUT_SECONDS = 600
QUALITY = "l"  # 854x480 at 15 fps
LOG_TAIL_LINES = 15
PARAMS_ENV = "PIPELINE_SCENE_PARAMS"
FACTS_ENV = "PIPELINE_RENDER_FACTS"
SECRET_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")


def build_render_command(template_path: Path, media_dir: Path) -> list[str]:
    return [
        sys.executable, "-m", "manim", "render",
        "--quality", QUALITY,
        "--format", "mp4",
        "--media_dir", str(media_dir),
        "--output_file", Path(VIDEO_FILENAME).stem,
        "--disable_caching",
        "--progress_bar", "none",
        str(template_path),
        SCENE_CLASS,
    ]


def render_environment(base_env: Mapping[str, str], paths: ProjectPaths) -> dict[str, str]:
    env = {
        name: value
        for name, value in base_env.items()
        if not any(marker in name.upper() for marker in SECRET_MARKERS)
    }
    env[PARAMS_ENV] = str(paths.scene_params)
    env[FACTS_ENV] = str(paths.render_facts)
    env["PYTHONPATH"] = str(REPO_ROOT)  # lets the template import pipeline.functions
    return env


def _clear_previous_outputs(paths: ProjectPaths) -> None:
    # Only files this stage created; a failed render must not leave a stale video behind.
    shutil.rmtree(paths.manim_media_dir, ignore_errors=True)
    for path in (paths.video, paths.render_facts, paths.render_log):
        path.unlink(missing_ok=True)
    paths.renders_dir.mkdir(parents=True, exist_ok=True)


def _write_log(paths: ProjectPaths, command: list[str], stdout: str, stderr: str) -> None:
    paths.render_log.write_text(
        f"$ {' '.join(command)}\n\n--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}\n",
        encoding="utf-8",
    )


def _tail(text: str) -> str:
    return "\n".join(text.strip().splitlines()[-LOG_TAIL_LINES:])


def write_scene_params(paths: ProjectPaths) -> None:
    storyboard = read_model(paths.storyboard, Storyboard)
    params = SceneParams(
        template_file=TEMPLATE_FILE.name,
        template_sha256=file_sha256(TEMPLATE_FILE),
        scene_class=SCENE_CLASS,
        storyboard=storyboard,
    )
    write_model(paths.scene_params, params)


def run(paths: ProjectPaths) -> None:
    _clear_previous_outputs(paths)
    write_scene_params(paths)
    command = build_render_command(TEMPLATE_FILE, paths.manim_media_dir)
    try:
        result = subprocess.run(
            command,
            cwd=paths.renders_dir,
            env=render_environment(os.environ, paths),
            capture_output=True,
            text=True,
            timeout=RENDER_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        _write_log(paths, command, str(error.stdout or ""), str(error.stderr or ""))
        raise StageError(
            f"Manim render timed out after {RENDER_TIMEOUT_SECONDS} s. Log: {paths.render_log}"
        ) from error

    _write_log(paths, command, result.stdout, result.stderr)
    if result.returncode != 0:
        raise StageError(
            f"Manim failed with exit code {result.returncode}. Last log lines:\n"
            f"{_tail(result.stderr or result.stdout)}\nFull log: {paths.render_log}"
        )

    produced = sorted(
        path for path in paths.manim_media_dir.rglob(VIDEO_FILENAME)
        if "partial_movie_files" not in path.parts
    )
    if not produced:
        raise StageError(
            f"Manim exited successfully but no MP4 named {VIDEO_FILENAME} was found in "
            f"{paths.manim_media_dir}. Log: {paths.render_log}"
        )
    shutil.copy2(produced[0], paths.video)


def validate(paths: ProjectPaths) -> None:
    read_model(paths.render_facts, RenderFacts)
