"""Plan stage: brief.json -> storyboard.json.

Deterministic (no AI): the same brief always gives the same storyboard. Every
number shown on screen is computed from the whitelisted function, and the
math is checked here, before any rendering happens.
"""

import math

from pipeline.functions import (
    SupportedFunction,
    format_line_equation,
    format_number,
    get_function,
    secant_slope,
    tangent_line,
)
from pipeline.paths import ProjectPaths
from pipeline.runner import StageError
from pipeline.schemas import H_END, AxesSpec, Beat, Brief, BriefError, Storyboard, load_brief
from pipeline.stages._io import read_model, write_model
from pipeline.stages.quality_check import check_math

AXIS_PADDING = 1.0
MAX_TICKS = 10
CURVE_SAMPLES = 200

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
    return format_number(value).replace("-", "−")


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


def _script(fn: SupportedFunction, brief: Brief) -> dict[str, tuple[str, str]]:
    """beat name -> (on-screen caption, narration line), using computed values only."""
    x0, m = _num(brief.x0), _num(fn.derivative(brief.x0))
    y0 = _num(fn.f(brief.x0))
    end_slope = f"{secant_slope(fn, brief.x0, H_END):.2f}".replace("-", "−")
    return {
        "curve": (f"Our curve: {fn.label}", f"Here is the curve {fn.label}."),
        "point": (f"Zoom in on P = ({x0}, {y0})",
                  f"We want the steepness of the curve exactly at the point P = ({x0}, {y0})."),
        "secant": ("Q sits h to the right of P",
                   "Pick a second point Q, a distance h to the right, and draw the line through P and Q."),
        "secant_pause": ("Secant slope = (f(x₀+h) − f(x₀)) / h",
                         f"The slope of this secant line works out to {fn.secant_slope_label(brief.x0)}."),
        "shrink": ("Now let h shrink toward 0", "Now slide Q toward P by shrinking h."),
        "shrink_pause": (f"At h = {format_number(H_END)}: slope = {end_slope}",
                         f"With h = {format_number(H_END)} the secant slope is already {end_slope}."),
        "tangent": ("The secants become the tangent",
                    "In the limit, the secant lines become the tangent line."),
        "tangent_label": (f"So f′({x0}) = {m}",
                          f"So the derivative at x = {x0} is {m}: the slope of the tangent line."),
    }


def build_storyboard(brief: Brief) -> Storyboard:
    fn = get_function(brief.function)
    tangent = tangent_line(fn, brief.x0)
    y0 = fn.f(brief.x0)
    script = _script(fn, brief)
    beats = tuple(
        Beat(name=name, description=description, run_time=run_time,
             caption=script.get(name, ("", ""))[0], narration=script.get(name, ("", ""))[1])
        for name, description, run_time in BEAT_TIMING
    )
    objective = brief.objective or (
        f"See why the slope of {fn.label.removeprefix('f(x) = ')} at x = {_num(brief.x0)} "
        f"is {_num(tangent.slope)}, by watching secant lines turn into the tangent line."
    )
    return Storyboard(
        template="secant_tangent",
        format=brief.format,
        topic=brief.topic,
        learning_objective=objective,
        function=fn.expression,
        x0=brief.x0,
        y0=y0,
        h_start=brief.h_start,
        h_end=H_END,
        derivative=tangent.slope,
        tangent_intercept=tangent.intercept,
        secant_coefficients=fn.secant_coefficients(brief.x0),
        function_label=fn.label,
        point_label=f"P ({_num(brief.x0)}, {_num(y0)})",
        secant_slope_label=fn.secant_slope_label(brief.x0),
        tangent_label=f"Tangent: {format_line_equation(tangent)}",
        axes=compute_axes(fn, brief.x0, brief.h_start),
        beats=beats,
    )


def verify_storyboard(storyboard: Storyboard) -> None:
    """Check the math claims before rendering; raise StageError listing any failure."""
    failed = [f"{c.name}: {c.detail}" for c in check_math(storyboard) if c.status != "pass"]
    if failed:
        raise StageError("Storyboard math check failed before rendering:\n  " + "\n  ".join(failed))


def run(paths: ProjectPaths) -> None:
    try:
        brief = load_brief(paths.brief)
    except BriefError as error:
        raise StageError(str(error)) from error
    storyboard = build_storyboard(brief)
    verify_storyboard(storyboard)
    write_model(paths.storyboard, storyboard)


def validate(paths: ProjectPaths) -> None:
    read_model(paths.storyboard, Storyboard)
