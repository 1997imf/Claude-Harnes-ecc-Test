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
from pipeline.schemas import STORYBOARD_ADAPTER, RenderFacts, SceneParams
from pipeline.stages._io import read_model, write_model
from pipeline.visuals import VISUALS

REPO_ROOT = Path(__file__).resolve().parents[2]
RENDER_TIMEOUT_SECONDS = 600
RENDER_MAX_ATTEMPTS = 2  # one retry after clearing Manim's working files; no code is changed
QUALITY = "l"  # 15 fps; pixel size comes from the storyboard format
LOG_TAIL_LINES = 15
PARAMS_ENV = "PIPELINE_SCENE_PARAMS"
FACTS_ENV = "PIPELINE_RENDER_FACTS"
SECRET_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")


def build_render_command(
    template_path: Path, scene_class: str, media_dir: Path, resolution: tuple[int, int] = (854, 480)
) -> list[str]:
    return [
        sys.executable, "-m", "manim", "render",
        "--quality", QUALITY,
        "--resolution", f"{resolution[0]},{resolution[1]}",
        "--format", "mp4",
        "--media_dir", str(media_dir),
        "--output_file", Path(VIDEO_FILENAME).stem,
        "--disable_caching",
        "--progress_bar", "none",
        str(template_path),
        scene_class,
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


def _write_log(paths: ProjectPaths, command: list[str], stdout: str, stderr: str, attempt: int) -> None:
    with paths.render_log.open("a", encoding="utf-8") as log:
        log.write(
            f"=== attempt {attempt}/{RENDER_MAX_ATTEMPTS}\n$ {' '.join(command)}\n\n"
            f"--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}\n"
        )


def _tail(text: str) -> str:
    return "\n".join(text.strip().splitlines()[-LOG_TAIL_LINES:])


def write_scene_params(paths: ProjectPaths) -> SceneParams:
    """Pick the reviewed template for the storyboard's visual and record exactly which one."""
    storyboard = read_model(paths.storyboard, STORYBOARD_ADAPTER)
    visual = VISUALS[storyboard.template]
    params = SceneParams(
        template_file=str(visual.template_file),
        template_sha256=file_sha256(visual.template_file),
        scene_class=visual.scene_class,
        storyboard=storyboard,
    )
    write_model(paths.scene_params, params)
    return params


def run(paths: ProjectPaths) -> None:
    _clear_previous_outputs(paths)
    params = write_scene_params(paths)
    command = build_render_command(Path(params.template_file), params.scene_class,
                                   paths.manim_media_dir, params.storyboard.resolution)
    errors = []
    for attempt in range(1, RENDER_MAX_ATTEMPTS + 1):
        shutil.rmtree(paths.manim_media_dir, ignore_errors=True)  # stale partial files cause retries to fail
        error = _render_once(paths, command, attempt)
        if error is None:
            return
        errors.append(f"attempt {attempt}: {error}")
    raise StageError(f"Render failed after {RENDER_MAX_ATTEMPTS} attempts.\n" + "\n".join(errors))


def _render_once(paths: ProjectPaths, command: list[str], attempt: int) -> str | None:
    """Run Manim once; return an error message, or None after copying the MP4 into place."""
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
        _write_log(paths, command, str(error.stdout or ""), str(error.stderr or ""), attempt)
        return f"Manim render timed out after {RENDER_TIMEOUT_SECONDS} s. Log: {paths.render_log}"

    _write_log(paths, command, result.stdout, result.stderr, attempt)
    if result.returncode != 0:
        return (
            f"Manim failed with exit code {result.returncode}. Last log lines:\n"
            f"{_tail(result.stderr or result.stdout)}\nFull log: {paths.render_log}"
        )

    produced = sorted(
        path for path in paths.manim_media_dir.rglob(VIDEO_FILENAME)
        if "partial_movie_files" not in path.parts
    )
    if not produced:
        return (
            f"Manim exited successfully but no MP4 named {VIDEO_FILENAME} was found in "
            f"{paths.manim_media_dir}. Log: {paths.render_log}"
        )
    shutil.copy2(produced[0], paths.video)
    return None


def validate(paths: ProjectPaths) -> None:
    read_model(paths.render_facts, RenderFacts)
