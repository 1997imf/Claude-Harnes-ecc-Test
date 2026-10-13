"""Shared test fixtures."""

import json
from pathlib import Path

import av
import numpy as np
import pytest

from pipeline.paths import ProjectPaths

EXAMPLE_BRIEF = {
    "topic": "Derivative as the limit of secants",
    "function": "x**2",
    "x0": 1,
    "h_start": 1.5,
}


def write_brief(project_dir: Path, brief: dict | None = None) -> ProjectPaths:
    project_dir.mkdir(parents=True, exist_ok=True)
    brief_path = project_dir / "brief.json"
    brief_path.write_text(json.dumps(brief or EXAMPLE_BRIEF))
    return ProjectPaths.from_brief(brief_path)


def make_video(path: Path, *, width=854, height=480, fps=15, seconds=2.0, value=128) -> Path:
    """Write a small solid-colour H.264 MP4 using PyAV (no ffmpeg executable needed)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with av.open(str(path), mode="w") as container:
        stream = container.add_stream("libx264", rate=fps)
        stream.width, stream.height, stream.pix_fmt = width, height, "yuv420p"
        image = np.full((height, width, 3), value, dtype=np.uint8)
        for _ in range(int(seconds * fps)):
            frame = av.VideoFrame.from_ndarray(image, format="rgb24")
            container.mux(stream.encode(frame))
        container.mux(stream.encode())
    return path


@pytest.fixture
def example_project(tmp_path) -> ProjectPaths:
    return write_brief(tmp_path / "derivative-x2")
