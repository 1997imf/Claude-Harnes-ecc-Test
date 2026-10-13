"""Plan stage: brief.json -> storyboard.json.

Deterministic for now (no AI): the same brief always gives the same storyboard.
"""

import math

from pipeline.functions import (
    SupportedFunction,
    format_line_equation,
    format_number,
    get_function,
    tangent_line,
)
from pipeline.paths import ProjectPaths
from pipeline.runner import StageError
from pipeline.schemas import H_END, AxesSpec, Beat, Brief, BriefError, Storyboard, load_brief
from pipeline.stages._io import read_model, write_model

AXIS_PADDING = 1.0
MAX_TICKS = 10
CURVE_SAMPLES = 200

BEATS = (
    Beat(name="title", description="Show the topic as the title", run_time=1.0),
    Beat(name="axes", description="Draw the coordinate axes", run_time=1.5),
    Beat(name="curve", description="Draw the curve and its label", run_time=1.5),
    Beat(name="point", description="Mark the point P = (x0, f(x0))", run_time=1.0),
    Beat(name="secant", description="Add Q = (x0 + h, f(x0 + h)) and the secant PQ", run_time=1.5),
    Beat(name="secant_pause", description="Let the viewer read the slope", run_time=1.0),
    Beat(name="shrink", description="Shrink h toward 0; Q slides to P", run_time=6.0),
    Beat(name="shrink_pause", description="Pause at the smallest h", run_time=1.0),
    Beat(name="tangent", description="Replace the secant with the tangent line", run_time=1.5),
    Beat(name="tangent_label", description="Write the tangent equation", run_time=1.0),
    Beat(name="hold", description="Hold the final frame", run_time=2.0),
)


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


def build_storyboard(brief: Brief) -> Storyboard:
    fn = get_function(brief.function)
    tangent = tangent_line(fn, brief.x0)
    y0 = fn.f(brief.x0)
    return Storyboard(
        template="secant_tangent",
        topic=brief.topic,
        function=fn.expression,
        x0=brief.x0,
        y0=y0,
        h_start=brief.h_start,
        h_end=H_END,
        derivative=tangent.slope,
        tangent_intercept=tangent.intercept,
        function_label=fn.label,
        point_label=f"P ({format_number(brief.x0)}, {format_number(y0)})",
        secant_slope_label=fn.secant_slope_label(brief.x0),
        tangent_label=f"Tangent: {format_line_equation(tangent)}",
        axes=compute_axes(fn, brief.x0, brief.h_start),
        beats=BEATS,
    )


def run(paths: ProjectPaths) -> None:
    try:
        brief = load_brief(paths.brief)
    except BriefError as error:
        raise StageError(str(error)) from error
    write_model(paths.storyboard, build_storyboard(brief))


def validate(paths: ProjectPaths) -> None:
    read_model(paths.storyboard, Storyboard)
