"""Parameterized secant-to-tangent scene, adapted from animations/secant_tangent.

Run by the render stage via `python -m manim`. Reads its parameters from the
JSON file named in PIPELINE_SCENE_PARAMS and writes the values it actually drew
to PIPELINE_RENDER_FACTS, so the QA stage can compare them with the storyboard.
Uses only Text (no MathTex/Tex), so LaTeX is not required.
"""

import os
from pathlib import Path

from manim import (
    BLUE, DOWN, DR, GREEN, GREY_B, LEFT, ORANGE, RIGHT, UL, UP, WHITE, YELLOW,
    Axes, Create, Dot, FadeIn, FadeOut, Line, Scene, Text, ValueTracker, VGroup, Write,
    always_redraw, config, smooth,
)

from pipeline.functions import LineEquation, clip_line_to_box, get_function, secant_slope
from pipeline.schemas import RenderFacts, SceneParams

PARAMS_ENV = "PIPELINE_SCENE_PARAMS"
FACTS_ENV = "PIPELINE_RENDER_FACTS"

AXES_WIDTH = 7.0
AXES_HEIGHT = 6.0
LABEL_FONT_SIZE = 28
TITLE_FONT_SIZE = 36
TITLE_MARGIN = 1.0
LINE_STROKE_WIDTH = 4
PANEL_TOP_OFFSET = 0.9
TANGENT_PANEL_OFFSET = 2.1
CURVE_LABEL_INSET = 0.4

CURVE_COLOR = BLUE
POINT_COLOR = YELLOW
SECANT_COLOR = ORANGE
TANGENT_COLOR = GREEN


def _load_params() -> SceneParams:
    path = os.environ.get(PARAMS_ENV)
    if not path:
        raise RuntimeError(f"{PARAMS_ENV} is not set; run this scene through the pipeline")
    return SceneParams.model_validate_json(Path(path).read_text(encoding="utf-8"))


class SecantTangentTemplate(Scene):
    def construct(self) -> None:
        board = _load_params().storyboard
        self.board = board
        self.fn = get_function(board.function)
        self.axes = self._build_axes()
        labels: list[str] = []

        title = Text(board.topic, font_size=TITLE_FONT_SIZE, color=WHITE).to_edge(UP)
        if title.width > config.frame_width - TITLE_MARGIN:
            title.scale_to_fit_width(config.frame_width - TITLE_MARGIN)
        self.play(Write(title), run_time=board.run_time("title"))
        self.play(Create(self.axes), run_time=board.run_time("axes"))

        point = self._show_curve_and_point(labels)
        h = ValueTracker(board.h_start)
        secant, q_dot, q_label, panel = self._build_secant_parts(h, labels)
        point.set_z_index(1)
        self.play(Create(secant), FadeIn(q_dot, q_label), FadeIn(panel),
                  run_time=board.run_time("secant"))
        self.wait(board.run_time("secant_pause"))

        self.play(h.animate.set_value(board.h_end), run_time=board.run_time("shrink"), rate_func=smooth)
        self.wait(board.run_time("shrink_pause"))
        final_secant = secant.copy()

        tangent = self._show_tangent(VGroup(secant, q_dot, q_label), labels)
        self.wait(board.run_time("hold"))
        self._write_facts(point, tangent, final_secant, h.get_value(), labels)

    def _build_axes(self) -> Axes:
        spec = self.board.axes
        # Tick numbers stay off: Manim renders them with LaTeX.
        axes = Axes(
            x_range=(spec.x_min, spec.x_max, spec.x_step),
            y_range=(spec.y_min, spec.y_max, spec.y_step),
            x_length=AXES_WIDTH, y_length=AXES_HEIGHT,
            axis_config={"color": GREY_B, "include_numbers": False}, tips=True,
        )
        return axes.to_edge(DOWN, buff=0.4)

    def _show_curve_and_point(self, labels: list[str]) -> Dot:
        board, axes = self.board, self.axes
        curve = axes.plot(self.fn.f, x_range=(board.axes.x_min, board.axes.x_max), color=CURVE_COLOR)
        label_x = board.axes.x_max - CURVE_LABEL_INSET
        curve_label = Text(board.function_label, font_size=LABEL_FONT_SIZE, color=CURVE_COLOR)
        curve_label.next_to(axes.c2p(label_x, min(self.fn.f(label_x), board.axes.y_max)), UL, buff=0.15)
        point = Dot(axes.c2p(board.x0, board.y0), color=POINT_COLOR)
        point_label = Text(board.point_label, font_size=LABEL_FONT_SIZE, color=POINT_COLOR)
        point_label.next_to(point, DR, buff=0.15)
        labels += [board.function_label, board.point_label]
        self.play(Create(curve), FadeIn(curve_label), run_time=board.run_time("curve"))
        self.play(FadeIn(point, scale=1.5), FadeIn(point_label), run_time=board.run_time("point"))
        return point

    def _line_through_p(self, slope: float, color) -> Line:
        board = self.board
        line = LineEquation(slope, board.y0 - slope * board.x0)
        x_low, x_high = clip_line_to_box(
            line, (board.axes.x_min, board.axes.x_max), (board.axes.y_min, board.axes.y_max)
        )
        return Line(self.axes.c2p(x_low, line.at(x_low)), self.axes.c2p(x_high, line.at(x_high)),
                    color=color, stroke_width=LINE_STROKE_WIDTH)

    def _build_secant_parts(self, h: ValueTracker, labels: list[str]):
        board, axes, fn = self.board, self.axes, self.fn

        def q_point():
            q_x = board.x0 + h.get_value()
            return axes.c2p(q_x, fn.f(q_x))

        secant = always_redraw(
            lambda: self._line_through_p(secant_slope(fn, board.x0, h.get_value()), SECANT_COLOR)
        )
        q_dot = always_redraw(lambda: Dot(q_point(), color=SECANT_COLOR).set_z_index(1))
        q_label = always_redraw(
            lambda: Text("Q", font_size=LABEL_FONT_SIZE, color=SECANT_COLOR).next_to(q_point(), RIGHT, buff=0.15)
        )
        formula = Text(board.secant_slope_label, font_size=LABEL_FONT_SIZE, color=SECANT_COLOR)
        formula.to_corner(UL).shift(DOWN * PANEL_TOP_OFFSET)
        readout = always_redraw(
            lambda: Text(
                f"h = {h.get_value():.2f}   Slope = {secant_slope(fn, board.x0, h.get_value()):.2f}",
                font_size=LABEL_FONT_SIZE, color=WHITE,
            ).next_to(formula, DOWN, aligned_edge=LEFT)
        )
        labels.append(board.secant_slope_label)
        return secant, q_dot, q_label, VGroup(formula, readout)

    def _show_tangent(self, fade_out: VGroup, labels: list[str]) -> Line:
        board = self.board
        tangent = self._line_through_p(board.derivative, TANGENT_COLOR)
        limit_text = f"h → 0,  Slope → {board.derivative:g}"
        tangent_label = VGroup(
            Text(board.tangent_label, font_size=LABEL_FONT_SIZE, color=TANGENT_COLOR),
            Text(limit_text, font_size=LABEL_FONT_SIZE, color=TANGENT_COLOR),
        ).arrange(DOWN, aligned_edge=LEFT)
        tangent_label.to_corner(UL).shift(DOWN * TANGENT_PANEL_OFFSET)
        labels += [board.tangent_label, limit_text]
        self.play(Create(tangent), FadeOut(fade_out), run_time=board.run_time("tangent"))
        self.play(Write(tangent_label), run_time=board.run_time("tangent_label"))
        return tangent

    def _measured_line(self, line: Line) -> LineEquation:
        """Slope and intercept measured back from the drawn line's endpoints."""
        x1, y1 = self.axes.p2c(line.get_start())[:2]
        x2, y2 = self.axes.p2c(line.get_end())[:2]
        slope = (y2 - y1) / (x2 - x1)
        return LineEquation(slope, y1 - slope * x1)

    def _write_facts(self, point: Dot, tangent: Line, final_secant: Line, final_h: float,
                     labels: list[str]) -> None:
        path = os.environ.get(FACTS_ENV)
        if not path:
            return
        drawn_tangent = self._measured_line(tangent)
        px, py = self.axes.p2c(point.get_center())[:2]
        facts = RenderFacts(
            point=(float(px), float(py)),
            tangent_slope=float(drawn_tangent.slope),
            tangent_intercept=float(drawn_tangent.intercept),
            final_h=float(final_h),
            final_secant_slope=float(self._measured_line(final_secant).slope),
            labels=labels,
        )
        Path(path).write_text(facts.model_dump_json(indent=2), encoding="utf-8")
