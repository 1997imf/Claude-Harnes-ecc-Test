"""Secant-to-tangent visual: the derivative as the limit of secant slopes.

Moved from the plan and quality_check stages so each visual keeps its planning,
math checks, and expected drawn values in one place.
"""

import math

from pipeline.functions import (
    SupportedFunction,
    format_line_equation,
    format_number,
    format_secant_label,
    get_function,
    numeric_derivative,
    secant_slope,
    tangent_line,
    with_minus,
)
from pipeline.schemas import (
    H_END, AxesSpec, Beat, CheckResult, Definition, DerivativeClaim, Equation, LessonPlan,
    SecantBrief, SecantParams, SecantStoryboard,
)

AXIS_PADDING = 1.0
MAX_TICKS = 10
CURVE_SAMPLES = 200
MATH_TOLERANCE = 1e-6
SECANT_CONVERGENCE_TOLERANCE = 0.1
TAGS = ("math", "calculus", "derivative", "limits", "secant line", "tangent line", "manim")
SAMPLE_H = 0.5  # h used in the lesson's exact arithmetic check of the secant formula
# Names returned by check_math (a test keeps them in sync).
CHECK_NAMES = frozenset({"derivative", "tangent_line", "secant_converges", "secant_formula"})

# (name, description, run_time) in playback order; captions are filled in per brief.
BEAT_TIMING = (
    ("title", "Show the topic as the title", 1.0),
    ("axes", "Draw the coordinate axes", 1.5),
    ("curve", "Draw the curve and its label", 1.5),
    ("point", "Mark the point P = (x0, f(x0))", 1.0),
    ("secant", "Add Q = (x0 + h, f(x0 + h)) and the secant PQ", 1.5),
    ("secant_pause", "Let the viewer read the slope", 1.5),
    ("shrink", "Shrink h toward 0; Q slides to P", 6.0),
    ("shrink_pause", "Pause at the smallest h", 1.5),
    ("tangent", "Replace the secant with the tangent line", 1.5),
    ("tangent_label", "Write the tangent equation", 1.0),
    ("hold", "Hold the final frame", 2.0),
)


def _num(value: float) -> str:
    return with_minus(format_number(value))


def _tick_step(span: float) -> float:
    return float(max(1, math.ceil(span / MAX_TICKS)))


def compute_axes(fn: SupportedFunction, x0: float, h_start: float) -> AxesSpec:
    """Axes that always show the origin, P, and the starting position of Q."""
    q_x = x0 + h_start
    x_min = float(min(math.floor(min(x0, q_x) - AXIS_PADDING), -1))
    x_max = float(max(math.ceil(max(x0, q_x) + AXIS_PADDING / 2), 1))
    samples = [x_min + (x_max - x_min) * i / CURVE_SAMPLES for i in range(CURVE_SAMPLES + 1)]
    values = [fn.f(x) for x in samples]
    y_min = float(min(math.floor(min(values)), 0) - 1)
    y_max = float(math.ceil(max(values)) + 1)
    return AxesSpec(
        x_min=x_min, x_max=x_max, x_step=_tick_step(x_max - x_min),
        y_min=y_min, y_max=y_max, y_step=_tick_step(y_max - y_min),
    )


def _script(fn: SupportedFunction, params: SecantParams) -> dict[str, tuple[str, str]]:
    """beat name -> (on-screen caption, narration line), using computed values only."""
    x0, m = _num(params.x0), _num(fn.derivative(params.x0))
    y0 = _num(fn.f(params.x0))
    end_slope = with_minus(f"{secant_slope(fn, params.x0, H_END):.2f}")
    return {
        "curve": (f"Our curve: {fn.label}", f"Here is the curve {fn.label}."),
        "point": (f"Zoom in on P = ({x0}, {y0})",
                  f"We want the steepness of the curve exactly at the point P = ({x0}, {y0})."),
        "secant": ("Q sits h to the right of P",
                   "Pick a second point Q, a distance h to the right, and draw the line through P and Q."),
        "secant_pause": ("Secant slope = (f(x₀+h) − f(x₀)) / h",
                         f"The slope of this secant line works out to {fn.secant_slope_label(params.x0)}."),
        "shrink": ("Now let h shrink toward 0", "Now slide Q toward P by shrinking h."),
        "shrink_pause": (f"At h = {format_number(H_END)}: slope = {end_slope}",
                         f"With h = {format_number(H_END)} the secant slope is already {end_slope}."),
        "tangent": ("The secants become the tangent",
                    "In the limit, the secant lines become the tangent line."),
        "tangent_label": (f"So f′({x0}) = {m}",
                          f"So the derivative at x = {x0} is {m}: the slope of the tangent line."),
    }


def _substitute(fn: SupportedFunction, x: float) -> str:
    """The allowlisted expression with x replaced by a number, for exact arithmetic checks."""
    return fn.expression.replace("x", f"({x!r})")


def build_lesson(brief: SecantBrief) -> LessonPlan:
    """Deterministic lesson plan for a classic secant-tangent brief."""
    fn = get_function(brief.function)
    params = SecantParams(function=fn.expression, x0=brief.x0, h_start=brief.h_start)
    tangent = tangent_line(fn, brief.x0)
    script = _script(fn, params)
    a, b, c = fn.secant_coefficients(brief.x0)
    x0, h = brief.x0, SAMPLE_H
    objective = brief.objective or (
        f"See why the slope of {fn.label.removeprefix('f(x) = ')} at x = {_num(x0)} "
        f"is {_num(tangent.slope)}, by watching secant lines turn into the tangent line."
    )
    return LessonPlan(
        topic=brief.topic,
        learning_objective=objective,
        audience="high_school",
        definitions=(
            Definition(term="secant line", meaning="a line through two points of a curve"),
            Definition(term="tangent line", meaning="the line that touches the curve at one point "
                                                    "with the same steepness as the curve there"),
            Definition(term="derivative", meaning="f′(x₀) = the limit of (f(x₀ + h) − f(x₀)) / h as h → 0"),
        ),
        equations=(
            Equation(display=f"(f(x₀ + h) − f(x₀)) / h = {fn.secant_slope_label(x0).removeprefix('Slope = ')}",
                     arithmetic=f"(({_substitute(fn, x0 + h)}) - ({_substitute(fn, x0)})) / {h!r} "
                                f"== {a!r} + {b!r}*{h!r} + {c!r}*{h!r}**2"),
            Equation(display=format_line_equation(tangent),
                     arithmetic=f"{tangent.slope!r}*({x0!r}) + ({tangent.intercept!r}) == {_substitute(fn, x0)}"),
        ),
        results=(DerivativeClaim(kind="derivative", function=fn.expression, at=x0, value=tangent.slope),),
        steps=tuple(script[name][1] for name, _, _ in BEAT_TIMING if name in script),
        examples=(
            f"With h = {format_number(brief.h_start)} the secant slope is "
            f"{_num(secant_slope(fn, x0, brief.h_start))}.",
            f"With h = {format_number(H_END)} it is {_num(round(secant_slope(fn, x0, H_END), 6))}.",
        ),
        conclusion=f"f′({_num(x0)}) = {_num(tangent.slope)}; the tangent line at P is "
                   f"{format_line_equation(tangent)}.",
        visualization=params,
        required_checks=tuple(sorted(CHECK_NAMES)) + ("rendered_values",),
    )


def build_storyboard(lesson: LessonPlan, video_format: str) -> SecantStoryboard:
    params = lesson.visualization
    fn = get_function(params.function)
    tangent = tangent_line(fn, params.x0)
    y0 = fn.f(params.x0)
    script = _script(fn, params)
    beats = tuple(
        Beat(name=name, description=description, run_time=run_time,
             caption=script.get(name, ("", ""))[0], narration=script.get(name, ("", ""))[1])
        for name, description, run_time in BEAT_TIMING
    )
    return SecantStoryboard(
        template="secant_tangent",
        format=video_format,
        topic=lesson.topic,
        learning_objective=lesson.learning_objective,
        result=f"f′({_num(params.x0)}) = {_num(tangent.slope)} for {fn.label}",
        tags=TAGS,
        function=fn.expression,
        x0=params.x0,
        y0=y0,
        h_start=params.h_start,
        h_end=H_END,
        derivative=tangent.slope,
        tangent_intercept=tangent.intercept,
        secant_coefficients=fn.secant_coefficients(params.x0),
        function_label=fn.label,
        point_label=f"P ({_num(params.x0)}, {_num(y0)})",
        secant_slope_label=fn.secant_slope_label(params.x0),
        tangent_label=f"Tangent: {format_line_equation(tangent)}",
        axes=compute_axes(fn, params.x0, params.h_start),
        beats=beats,
    )


def check_math(storyboard: SecantStoryboard) -> list[CheckResult]:
    fn = get_function(storyboard.function)
    x0 = storyboard.x0
    exact = fn.derivative(x0)
    numeric = numeric_derivative(fn, x0)
    tangent = tangent_line(fn, x0)
    start_error = abs(secant_slope(fn, x0, storyboard.h_start) - exact)
    end_error = abs(secant_slope(fn, x0, storyboard.h_end) - exact)
    expected_label = f"Tangent: {format_line_equation(tangent)}"
    a, b, c = storyboard.secant_coefficients
    formula_errors = [
        abs(a + b * h + c * h * h - secant_slope(fn, x0, h))
        for h in (storyboard.h_start, storyboard.h_start / 3, storyboard.h_end)
    ]
    return [
        CheckResult.of("derivative",
                       abs(storyboard.derivative - exact) <= MATH_TOLERANCE
                       and abs(numeric - exact) <= MATH_TOLERANCE,
                       f"f'({x0:g}) storyboard={storyboard.derivative:g}, exact={exact:g}, numeric={numeric:.6f}"),
        CheckResult.of("tangent_line",
                       abs(storyboard.tangent_intercept - tangent.intercept) <= MATH_TOLERANCE
                       and abs(storyboard.y0 - fn.f(x0)) <= MATH_TOLERANCE
                       and storyboard.tangent_label == expected_label,
                       f"expected {expected_label}, storyboard says {storyboard.tangent_label!r} "
                       f"(intercept {storyboard.tangent_intercept:g})"),
        CheckResult.of("secant_converges",
                       end_error < start_error and end_error <= SECANT_CONVERGENCE_TOLERANCE,
                       f"|secant − f'| goes from {start_error:.4f} (h={storyboard.h_start:g}) "
                       f"to {end_error:.4f} (h={storyboard.h_end:g})"),
        CheckResult.of("secant_formula",
                       max(formula_errors) <= MATH_TOLERANCE
                       and storyboard.secant_slope_label == format_secant_label(storyboard.secant_coefficients)
                       and abs(a - exact) <= MATH_TOLERANCE,
                       f"on-screen {storyboard.secant_slope_label!r} matches the difference quotient "
                       f"(max error {max(formula_errors):.1e}) and equals f'(x0) at h = 0"),
    ]


def expected_values(storyboard: SecantStoryboard) -> dict[str, float]:
    return {
        "point_x": storyboard.x0,
        "point_y": storyboard.y0,
        "tangent_slope": storyboard.derivative,
        "tangent_intercept": storyboard.tangent_intercept,
        "final_h": storyboard.h_end,
    }


def expected_labels(storyboard: SecantStoryboard) -> set[str]:
    return {storyboard.function_label, storyboard.point_label,
            storyboard.secant_slope_label, storyboard.tangent_label}
