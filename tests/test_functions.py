"""Tests for the whitelisted math functions and line helpers."""

import math

import pytest

from pipeline.functions import (
    LineEquation,
    clip_line_to_box,
    format_line_equation,
    format_number,
    get_function,
    numeric_derivative,
    secant_slope,
    tangent_line,
)


def test_get_function_returns_square_for_supported_expression():
    fn = get_function("x**2")

    assert fn.expression == "x**2"
    assert fn.f(3.0) == 9.0
    assert fn.derivative(3.0) == 6.0


def test_get_function_ignores_whitespace():
    assert get_function(" x ** 2 ").expression == "x**2"


@pytest.mark.parametrize(
    "expression",
    ["x**4", "sin(x)", "__import__('os').system('ls')", "", "x^2"],
)
def test_get_function_rejects_unsupported_expressions(expression):
    with pytest.raises(ValueError, match="Unsupported function"):
        get_function(expression)


def test_unsupported_function_error_lists_supported_functions():
    with pytest.raises(ValueError, match=r"Supported: x\*\*2, x\*\*3"):
        get_function("x**4")


@pytest.mark.parametrize("x0, h", [(1.0, 1.5), (1.0, 0.01), (-2.0, 0.5), (0.0, 1.0)])
def test_secant_slope_of_square_equals_two_x0_plus_h(x0, h):
    assert secant_slope(get_function("x**2"), x0, h) == pytest.approx(2 * x0 + h)


def test_secant_slope_rejects_zero_h():
    with pytest.raises(ValueError, match="h must be non-zero"):
        secant_slope(get_function("x**2"), 1.0, 0.0)


@pytest.mark.parametrize(
    "x0, slope, intercept",
    [(1.0, 2.0, -1.0), (-2.0, -4.0, -4.0), (0.0, 0.0, 0.0), (1.5, 3.0, -2.25)],
)
def test_tangent_line_of_square(x0, slope, intercept):
    line = tangent_line(get_function("x**2"), x0)

    assert line.slope == pytest.approx(slope)
    assert line.intercept == pytest.approx(intercept)
    assert line.at(x0) == pytest.approx(x0**2)


def test_numeric_derivative_agrees_with_exact_derivative():
    fn = get_function("x**2")

    assert numeric_derivative(fn, 1.0) == pytest.approx(2.0, abs=1e-6)


def test_clip_line_keeps_steep_line_inside_y_range():
    line = LineEquation(slope=3.5, intercept=-2.5)

    x_low, x_high = clip_line_to_box(line, (-1.0, 3.0), (-1.0, 9.0))

    assert x_low == pytest.approx(3 / 7)
    assert x_high == pytest.approx(3.0)
    assert -1.0 <= line.at(x_low) <= 9.0
    assert -1.0 <= line.at(x_high) <= 9.0


def test_clip_line_with_zero_slope_spans_full_x_range():
    assert clip_line_to_box(LineEquation(0.0, 1.0), (-1.0, 3.0), (-1.0, 9.0)) == (-1.0, 3.0)


def test_clip_line_rejects_line_that_misses_the_box():
    with pytest.raises(ValueError, match="does not cross"):
        clip_line_to_box(LineEquation(0.0, 20.0), (-1.0, 3.0), (-1.0, 9.0))


@pytest.mark.parametrize(
    "value, text", [(2.0, "2"), (-1.0, "-1"), (0.25, "0.25"), (-0.0, "0"), (1e-15, "0")]
)
def test_format_number(value, text):
    assert format_number(value) == text


@pytest.mark.parametrize(
    "slope, intercept, text",
    [
        (2.0, -1.0, "y = 2x − 1"),
        (-4.0, -4.0, "y = −4x − 4"),
        (1.0, -0.25, "y = x − 0.25"),
        (-1.0, 2.0, "y = −x + 2"),
        (0.0, 0.0, "y = 0"),
        (0.0, 3.0, "y = 3"),
        (3.0, 0.0, "y = 3x"),
    ],
)
def test_format_line_equation(slope, intercept, text):
    assert format_line_equation(LineEquation(slope, intercept)) == text


def test_secant_label_for_square_shows_two_x0_plus_h():
    fn = get_function("x**2")

    assert fn.secant_slope_label(1.0) == "Slope = 2 + h"
    assert fn.secant_slope_label(-2.0) == "Slope = −4 + h"
    assert fn.secant_slope_label(0.0) == "Slope = h"


@pytest.mark.parametrize(
    "x0, label", [(1.0, "Slope = 3 + 3h + h²"), (-1.0, "Slope = 3 − 3h + h²"), (0.0, "Slope = h²")]
)
def test_secant_label_for_cube(x0, label):
    assert get_function("x**3").secant_slope_label(x0) == label


@pytest.mark.parametrize("expression", ["x**2", "x**3"])
@pytest.mark.parametrize("x0", [-2.0, -1.0, 0.0, 1.0, 2.5])
def test_secant_coefficients_match_the_actual_secant_slope(expression, x0):
    # The on-screen formula must agree with the real difference quotient.
    fn = get_function(expression)
    a, b, c = fn.secant_coefficients(x0)
    for h in (1.5, 0.3, 0.01):
        assert a + b * h + c * h * h == pytest.approx(secant_slope(fn, x0, h))


def test_square_is_finite_for_supported_range():
    assert math.isfinite(get_function("x**2").f(1e3))
