"""Tests for quality checks on videos, math, and rendered values."""

import json

import pytest

from pipeline.schemas import Brief, RenderFacts
from pipeline.stages.plan import build_storyboard
from pipeline.stages.quality_check import (
    check_math,
    check_rendered_values,
    inspect_video,
    run_quality_checks,
)
from tests.conftest import EXAMPLE_BRIEF, make_video

STORYBOARD = build_storyboard(Brief.model_validate(EXAMPLE_BRIEF))


def _facts(**changes):
    values = {
        "point": (1.0, 1.0),
        "tangent_slope": 2.0,
        "tangent_intercept": -1.0,
        "final_h": STORYBOARD.h_end,
        "final_secant_slope": 2.0 + STORYBOARD.h_end,
        "labels": [
            STORYBOARD.function_label,
            STORYBOARD.point_label,
            STORYBOARD.secant_slope_label,
            STORYBOARD.tangent_label,
            *(beat.caption for beat in STORYBOARD.beats if beat.caption),
        ],
    }
    return RenderFacts.model_validate({**values, **changes})


def _write_facts(tmp_path, facts):
    path = tmp_path / "render_facts.json"
    path.write_text(facts.model_dump_json())
    return path


def _by_name(checks):
    return {check.name: check for check in checks}


def test_missing_video_fails_existence_check(tmp_path):
    report = run_quality_checks(tmp_path / "none.mp4", STORYBOARD, tmp_path / "facts.json")

    checks = _by_name(report.checks)
    assert not report.passed
    assert checks["video_file"].status == "fail"
    assert checks["video_decodes"].status == "fail"


def test_empty_video_file_fails(tmp_path):
    video = tmp_path / "empty.mp4"
    video.write_bytes(b"")

    checks = _by_name(run_quality_checks(video, STORYBOARD, tmp_path / "f.json").checks)

    assert checks["video_file"].status == "fail" and "empty" in checks["video_file"].detail


def test_garbage_bytes_fail_decoding(tmp_path):
    video = tmp_path / "bad.mp4"
    video.write_bytes(b"this is not a video" * 100)

    check, info = inspect_video(video)

    assert check.status == "fail" and info is None


def test_valid_small_video_is_decoded_with_correct_metadata(tmp_path):
    video = make_video(tmp_path / "ok.mp4", seconds=2.0)

    check, info = inspect_video(video)

    assert check.status == "pass"
    assert (info.width, info.height) == (854, 480)
    assert info.duration == pytest.approx(2.0, abs=0.1)
    assert len(info.sample_frames) == 3


def test_wrong_resolution_and_duration_fail(tmp_path):
    video = make_video(tmp_path / "small.mp4", width=320, height=240, seconds=2.0)
    facts = _write_facts(tmp_path, _facts())

    checks = _by_name(run_quality_checks(video, STORYBOARD, facts).checks)

    assert checks["resolution"].status == "fail"
    assert checks["duration"].status == "fail"


def test_black_frames_fail_blank_check(tmp_path):
    video = make_video(tmp_path / "black.mp4", value=0)
    facts = _write_facts(tmp_path, _facts())

    checks = _by_name(run_quality_checks(video, STORYBOARD, facts).checks)

    assert checks["frames_not_blank"].status == "fail"


def test_math_checks_pass_for_planned_storyboard():
    assert all(check.status == "pass" for check in check_math(STORYBOARD))


def test_math_checks_catch_wrong_derivative():
    tampered = STORYBOARD.model_copy(update={"derivative": 3.0})

    failed = [c.name for c in check_math(tampered) if c.status == "fail"]

    assert "derivative" in failed


def test_math_checks_catch_wrong_tangent_intercept():
    tampered = STORYBOARD.model_copy(update={"tangent_intercept": 0.0})

    failed = [c.name for c in check_math(tampered) if c.status == "fail"]

    assert "tangent_line" in failed


def test_rendered_values_pass_when_scene_matches_storyboard(tmp_path):
    check = check_rendered_values(STORYBOARD, _write_facts(tmp_path, _facts()))

    assert check.status == "pass"


@pytest.mark.parametrize(
    "changes, fragment",
    [
        ({"tangent_slope": 2.5}, "tangent slope"),
        ({"point": (1.2, 1.0)}, "point P"),
        ({"final_h": 0.5}, "final h"),
        ({"labels": ["f(x) = x²"]}, "missing labels"),
    ],
)
def test_rendered_values_fail_on_mismatch(tmp_path, changes, fragment):
    check = check_rendered_values(STORYBOARD, _write_facts(tmp_path, _facts(**changes)))

    assert check.status == "fail" and fragment in check.detail


def test_missing_render_facts_fail(tmp_path):
    check = check_rendered_values(STORYBOARD, tmp_path / "nope.json")

    assert check.status == "fail" and "not found" in check.detail


def test_invalid_render_facts_fail(tmp_path):
    path = tmp_path / "facts.json"
    path.write_text(json.dumps({"point": "nowhere"}))

    assert check_rendered_values(STORYBOARD, path).status == "fail"
