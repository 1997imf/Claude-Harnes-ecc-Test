"""Tests for the deterministic storyboard planner."""

import pytest

from pipeline.schemas import H_END, STORYBOARD_ADAPTER, SecantBrief
from pipeline.stages.plan import build_storyboard

EXAMPLE = SecantBrief(topic="Derivative as the limit of secants", function="x**2", x0=1, h_start=1.5)


def test_storyboard_contains_correct_math_for_example_brief():
    board = build_storyboard(EXAMPLE)

    assert board.template == "secant_tangent"
    assert board.x0 == 1.0 and board.y0 == 1.0
    assert board.derivative == pytest.approx(2.0)
    assert board.tangent_intercept == pytest.approx(-1.0)
    assert board.h_start == 1.5 and board.h_end == H_END


def test_storyboard_labels_are_derived_from_parameters():
    board = build_storyboard(EXAMPLE)

    assert board.function_label == "f(x) = x²"
    assert board.point_label == "P (1, 1)"
    assert board.secant_slope_label == "Slope = 2 + h"
    assert board.tangent_label == "Tangent: y = 2x − 1"


def test_axes_contain_both_points_and_the_origin():
    board = build_storyboard(EXAMPLE)
    axes = board.axes
    q_x = board.x0 + board.h_start

    assert axes.x_min <= min(0.0, board.x0) and axes.x_max >= q_x
    assert axes.y_min <= 0.0 and axes.y_max >= q_x**2


def test_axes_for_negative_x0_still_contain_origin_and_points():
    board = build_storyboard(SecantBrief(topic="t", function="x**2", x0=-2, h_start=1.5))
    axes = board.axes

    assert axes.x_min <= -2.0 and axes.x_max >= 0.0
    assert axes.y_max >= 4.0
    # Keep tick marks readable: no more than about a dozen per axis.
    assert (axes.y_max - axes.y_min) / axes.y_step <= 12


def test_beats_cover_the_whole_story_in_order():
    names = [beat.name for beat in build_storyboard(EXAMPLE).beats]

    assert names.index("secant") < names.index("shrink") < names.index("tangent")
    assert names[0] == "title" and names[-1] == "hold"


def test_expected_duration_is_sum_of_beats():
    board = build_storyboard(EXAMPLE)

    assert board.expected_duration == pytest.approx(sum(b.run_time for b in board.beats))
    assert 10 <= board.expected_duration <= 30


def test_storyboard_is_deterministic():
    assert build_storyboard(EXAMPLE) == build_storyboard(EXAMPLE)


def test_captions_use_computed_values():
    board = build_storyboard(SecantBrief(topic="t", function="x**3", x0=-1, h_start=1, format="portrait"))
    captions = {beat.name: beat.caption for beat in board.beats}

    assert captions["tangent_label"] == "So f′(−1) = 3"
    assert captions["point"] == "Zoom in on P = (−1, −1)"
    assert board.secant_slope_label == "Slope = 3 − 3h + h²"
    assert "slope of x³ at x = −1 is 3" in board.learning_objective


def test_pre_render_check_rejects_a_wrong_claim():
    from pipeline.runner import StageError
    from pipeline.stages.plan import verify_storyboard

    wrong = build_storyboard(EXAMPLE).model_copy(update={"secant_slope_label": "Slope = 3 + h"})

    with pytest.raises(StageError, match="secant_formula"):
        verify_storyboard(wrong)


def test_storyboard_round_trips_through_json():
    board = build_storyboard(EXAMPLE)

    assert STORYBOARD_ADAPTER.validate_json(board.model_dump_json()) == board


# --- other visual types ---------------------------------------------------------

from pipeline.schemas import OddSumBrief, PythagorasBrief  # noqa: E402


def test_pythagoras_storyboard_has_exact_areas():
    board = build_storyboard(PythagorasBrief(template="pythagoras", topic="t", a=5, b=12))

    assert (board.c, board.equation_label) == (13, "25 + 144 = 169")
    assert board.result == "5² + 12² = 13² (25 + 144 = 169)"


def test_pythagoras_check_rejects_wrong_equation_label():
    from pipeline.runner import StageError
    from pipeline.stages.plan import verify_storyboard

    board = build_storyboard(PythagorasBrief(template="pythagoras", topic="t", a=3, b=4))

    with pytest.raises(StageError, match="equation_label"):
        verify_storyboard(board.model_copy(update={"equation_label": "9 + 16 = 26"}))


def test_odd_sum_storyboard_running_sums():
    board = build_storyboard(OddSumBrief(template="odd_sum", topic="t", n=4))

    assert board.sum_labels == ("1", "1 + 3 = 4", "1 + 3 + 5 = 9", "1 + 3 + 5 + 7 = 16")
    assert board.partial_sums == (1, 4, 9, 16)


def test_odd_sum_check_rejects_wrong_running_sum():
    from pipeline.runner import StageError
    from pipeline.stages.plan import verify_storyboard

    board = build_storyboard(OddSumBrief(template="odd_sum", topic="t", n=3))
    wrong = board.model_copy(update={"sum_labels": ("1", "1 + 3 = 4", "1 + 3 + 5 = 10")})

    with pytest.raises(StageError, match="sum_labels"):
        verify_storyboard(wrong)
