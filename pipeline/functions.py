"""Whitelisted math functions and line helpers.

Expressions from a brief are only used as lookup keys in SUPPORTED_FUNCTIONS.
They are never evaluated, so a brief cannot run arbitrary Python.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import NamedTuple

NUMERIC_DERIVATIVE_STEP = 1e-5
ZERO_TOLERANCE = 1e-12
MINUS = "−"  # Unicode minus sign: renders better than "-" in on-screen labels


@dataclass(frozen=True)
class SupportedFunction:
    expression: str  # exact (whitespace-free) text accepted in brief.json
    label: str  # on-screen label, plain Text (no LaTeX)
    f: Callable[[float], float]
    derivative: Callable[[float], float]
    secant_slope_label: Callable[[float], str]  # x0 -> e.g. "Slope = 2 + h"


class LineEquation(NamedTuple):
    slope: float
    intercept: float

    def at(self, x: float) -> float:
        return self.slope * x + self.intercept


def format_number(value: float) -> str:
    """Compact number text: 2.0 -> "2", 0.25 -> "0.25", -0.0 -> "0"."""
    if abs(value) < ZERO_TOLERANCE:
        return "0"
    return f"{value:g}"


def _signed_term(value: float) -> str:
    """Format the second term of a sum, e.g. -1 -> " − 1", 0.5 -> " + 0.5"."""
    sign = MINUS if value < 0 else "+"
    return f" {sign} {format_number(abs(value))}"


def _square_secant_label(x0: float) -> str:
    # For f(x) = x^2: ((x0 + h)^2 - x0^2) / h = 2*x0 + h
    constant = 2 * x0
    if abs(constant) < ZERO_TOLERANCE:
        return "Slope = h"
    return f"Slope = {format_number(constant).replace('-', MINUS)} + h"


SUPPORTED_FUNCTIONS: dict[str, SupportedFunction] = {
    "x**2": SupportedFunction(
        expression="x**2",
        label="f(x) = x²",
        f=lambda x: x * x,
        derivative=lambda x: 2 * x,
        secant_slope_label=_square_secant_label,
    ),
}


def get_function(expression: str) -> SupportedFunction:
    """Look up a supported function; raise ValueError for anything else."""
    key = expression.replace(" ", "")
    if key not in SUPPORTED_FUNCTIONS:
        supported = ", ".join(SUPPORTED_FUNCTIONS)
        raise ValueError(f"Unsupported function {expression!r}. Supported: {supported}")
    return SUPPORTED_FUNCTIONS[key]


def secant_slope(fn: SupportedFunction, x0: float, h: float) -> float:
    if h == 0:
        raise ValueError("h must be non-zero: the secant slope divides by h")
    return (fn.f(x0 + h) - fn.f(x0)) / h


def tangent_line(fn: SupportedFunction, x0: float) -> LineEquation:
    slope = fn.derivative(x0)
    return LineEquation(slope=slope, intercept=fn.f(x0) - slope * x0)


def numeric_derivative(fn: SupportedFunction, x0: float) -> float:
    """Central finite difference: an independent check on fn.derivative."""
    step = NUMERIC_DERIVATIVE_STEP
    return (fn.f(x0 + step) - fn.f(x0 - step)) / (2 * step)


def clip_line_to_box(
    line: LineEquation, x_range: tuple[float, float], y_range: tuple[float, float]
) -> tuple[float, float]:
    """x-interval where the line stays inside the box (generalizes the original scene)."""
    x_min, x_max = x_range
    y_min, y_max = y_range
    if line.slope == 0:
        if not y_min <= line.intercept <= y_max:
            raise ValueError("Line does not cross the visible box")
        return x_min, x_max
    x_at_y_min = (y_min - line.intercept) / line.slope
    x_at_y_max = (y_max - line.intercept) / line.slope
    low, high = sorted((x_at_y_min, x_at_y_max))
    clipped = (max(x_min, low), min(x_max, high))
    if clipped[0] >= clipped[1]:
        raise ValueError("Line does not cross the visible box")
    return clipped


def format_line_equation(line: LineEquation) -> str:
    """Readable equation such as "y = 2x − 1" (Unicode minus, no LaTeX)."""
    slope, intercept = line
    if abs(slope) < ZERO_TOLERANCE:
        return f"y = {format_number(intercept).replace('-', MINUS)}"
    if abs(slope - 1) < ZERO_TOLERANCE:
        slope_text = "x"
    elif abs(slope + 1) < ZERO_TOLERANCE:
        slope_text = f"{MINUS}x"
    else:
        slope_text = f"{format_number(slope).replace('-', MINUS)}x"
    if abs(intercept) < ZERO_TOLERANCE:
        return f"y = {slope_text}"
    return f"y = {slope_text}{_signed_term(intercept)}"
