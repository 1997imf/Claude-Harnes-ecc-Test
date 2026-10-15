"""End-to-end test: real Manim render of the example brief at 480p.

Takes roughly a minute. Skip with: pytest -m "not integration"
"""

import json

import av
import pytest

from pipeline.cli import main
from tests.conftest import write_brief

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def rendered(tmp_path_factory):
    paths = write_brief(tmp_path_factory.mktemp("e2e") / "derivative-x2")
    exit_code = main(["run", str(paths.brief)])
    return paths, exit_code


def test_run_produces_playable_video(rendered):
    paths, exit_code = rendered

    assert exit_code == 0
    with av.open(str(paths.video)) as container:
        stream = container.streams.video[0]
        frames = sum(1 for _ in container.decode(stream))
        assert (stream.codec_context.width, stream.codec_context.height) == (854, 480)
    assert frames > 100


def test_qa_report_passes_and_includes_real_checks(rendered):
    paths, _ = rendered
    report = json.loads(paths.qa_report.read_text())

    names = {check["name"] for check in report["checks"]}
    assert report["passed"] is True
    assert {"video_decodes", "frames_not_blank", "derivative", "rendered_values", "lesson_plan"} <= names


def test_preview_points_at_existing_video(rendered):
    paths, _ = rendered
    html = paths.preview.read_text()

    assert 'src="renders/video.mp4"' in html
    assert (paths.preview.parent / "renders" / "video.mp4").is_file()


def test_rerun_and_resume_do_not_rerender(rendered, capsys):
    paths, _ = rendered
    mtime = paths.video.stat().st_mtime_ns
    capsys.readouterr()

    assert main(["run", str(paths.brief)]) == 0
    assert main(["resume", str(paths.brief)]) == 0

    out = capsys.readouterr().out
    assert "render: running" not in out
    assert out.count("render: up to date") == 2
    assert paths.video.stat().st_mtime_ns == mtime
