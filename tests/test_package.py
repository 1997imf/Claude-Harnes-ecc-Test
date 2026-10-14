"""Tests for the HTML preview page."""

from pipeline.schemas import SecantBrief, CheckResult, QAReport
from pipeline.stages.package import build_preview_html
from pipeline.stages.plan import build_storyboard
from tests.conftest import EXAMPLE_BRIEF

STORYBOARD = build_storyboard(SecantBrief.model_validate(EXAMPLE_BRIEF))


def _report(passed=True):
    status = "pass" if passed else "fail"
    return QAReport(
        passed=passed,
        video="renders/secant_tangent.mp4",
        checks=(CheckResult(name="duration", status=status, detail="18.5 s"),),
    )


def test_preview_embeds_video_with_relative_path():
    html = build_preview_html(STORYBOARD, _report(), "renders/secant_tangent.mp4")

    assert '<video controls src="renders/secant_tangent.mp4"' in html
    assert "<title>" in html


def test_preview_shows_topic_math_and_checks():
    html = build_preview_html(STORYBOARD, _report(), "renders/secant_tangent.mp4")

    assert "Derivative as the limit of secants" in html
    assert "f′(1) = 2 for f(x) = x²" in html
    assert "duration" in html and "18.5 s" in html
    assert "All checks passed" in html


def test_preview_flags_failed_checks():
    html = build_preview_html(STORYBOARD, _report(passed=False), "renders/x.mp4")

    assert "Some checks failed" in html


def test_metadata_fits_platform_limits_and_tags_shorts():
    from pipeline.stages.package import build_metadata

    portrait = STORYBOARD.model_copy(update={"format": "portrait"})

    meta = build_metadata(portrait, _report(), 480, 854, 20.07)

    assert meta.title == STORYBOARD.topic and len(meta.title) <= 100
    assert "#shorts" in meta.hashtags and len(meta.instagram_caption) <= 2200
    assert "f′(1) = 2" in meta.description
    assert (meta.width, meta.height, meta.duration_seconds) == (480, 854, 20.07)
    assert "#shorts" not in build_metadata(STORYBOARD, _report(), 854, 480, 20.0).hashtags


def test_preview_escapes_html_in_user_text():
    board = STORYBOARD.model_copy(update={"topic": "<script>alert(1)</script>"})

    html = build_preview_html(board, _report(), "renders/x.mp4")

    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html
