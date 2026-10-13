"""Tests for the deterministic storyboard planner."""

import pytest

from pipeline.schemas import Brief, Storyboard
from pipeline.stages.plan import H_END, build_storyboard

EXAMPLE = Brief(topic="Derivative as the limit of secants", function="x**2", x0=1, h_start=1.5)


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
    board = build_storyboard(Brief(topic="t", function="x**2", x0=-2, h_start=1.5))
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


def test_storyboard_round_trips_through_json():
    board = build_storyboard(EXAMPLE)

    assert Storyboard.model_validate_json(board.model_dump_json()) == board
