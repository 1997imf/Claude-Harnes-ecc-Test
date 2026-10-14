"""Parameterized secant-to-tangent scene, adapted from animations/secant_tangent.

Supports landscape (16:9) and portrait (9:16). Shared title/caption/facts
handling lives in _base.PipelineScene.
"""

from dataclasses import dataclass

from manim import (
    BLUE, DOWN, GREEN, GREY_B, LEFT, ORANGE, RIGHT, UL, UP, UR, WHITE, YELLOW,
    Axes, Create, Dot, FadeIn, FadeOut, Line, ValueTracker, VGroup, Write, always_redraw, smooth,
)

from pipeline.functions import (
    LineEquation, clip_line_to_box, format_number, get_function, secant_slope, with_minus,
)
from pipeline.templates._base import PipelineScene

LINE_STROKE_WIDTH = 4
CURVE_LABEL_INSET = 0.4
CURVE_COLOR = BLUE
POINT_COLOR = YELLOW
SECANT_COLOR = ORANGE
TANGENT_COLOR = GREEN


@dataclass(frozen=True)
class AxesLayout:
    width: float
    height: float
    bottom_buff: float


AXES_LAYOUTS = {"landscape": AxesLayout(7.0, 6.0, 0.4), "portrait": AxesLayout(4.0, 4.2, 0.5)}


class SecantTangentTemplate(PipelineScene):
    def construct(self) -> None:
        board = self.setup_board()
        self.fn = get_function(board.function)
        self.axes = self._build_axes()

        self.play_title()
        self.show_caption("axes")
        self.play(Create(self.axes), run_time=board.run_time("axes"))
        point = self._show_curve_and_point()

        h = ValueTracker(board.h_start)
        secant, q_dot, q_label, panel = self._build_secant_parts(h)
        point.set_z_index(1)
        self.show_caption("secant")
        self.play(Create(secant), FadeIn(q_dot, q_label), FadeIn(panel), run_time=board.run_time("secant"))
        self.show_caption("secant_pause")
        self.wait(board.run_time("secant_pause"))

        self.show_caption("shrink")
        self.play(h.animate.set_value(board.h_end), run_time=board.run_time("shrink"), rate_func=smooth)
        self.show_caption("shrink_pause")
        self.wait(board.run_time("shrink_pause"))
        final_secant = secant.copy()

        tangent = self._show_tangent(VGroup(secant, q_dot, q_label), panel)
        self.wait(board.run_time("hold"))
        self._record_measurements(point, tangent, final_secant, h.get_value())

    def _place_panel(self, mobject) -> None:
        if self.portrait:  # stacked under the caption, left-aligned
            mobject.next_to([0, self.caption_y - 0.25, 0], DOWN, buff=0.1)
            mobject.to_edge(LEFT, buff=self.text_layout.side_margin + 0.1)
        else:  # top-left corner, beside the axes
            mobject.to_corner(UL).shift(DOWN * 0.9)

    def _build_axes(self) -> Axes:
        spec, layout = self.board.axes, AXES_LAYOUTS[self.board.format]
        # Tick numbers stay off: Manim renders them with LaTeX.
        axes = Axes(
            x_range=(spec.x_min, spec.x_max, spec.x_step),
            y_range=(spec.y_min, spec.y_max, spec.y_step),
            x_length=layout.width, y_length=layout.height,
            axis_config={"color": GREY_B, "include_numbers": False}, tips=True,
        )
        return axes.to_edge(DOWN, buff=layout.bottom_buff)

    def _show_curve_and_point(self) -> Dot:
        board, axes = self.board, self.axes
        curve = axes.plot(self.fn.f, x_range=(board.axes.x_min, board.axes.x_max), color=CURVE_COLOR)
        # Label the curve near whichever end is higher, on the inner side of the curve.
        right_end_higher = self.fn.f(board.axes.x_max) >= self.fn.f(board.axes.x_min)
        label_x = (board.axes.x_max - CURVE_LABEL_INSET if right_end_higher
                   else board.axes.x_min + CURVE_LABEL_INSET)
        curve_label = self.label(board.function_label, CURVE_COLOR)
        curve_label.next_to(axes.c2p(label_x, min(self.fn.f(label_x), board.axes.y_max)),
                            UL if right_end_higher else UR, buff=0.15)
        point = Dot(axes.c2p(board.x0, board.y0), color=POINT_COLOR)
        # Secants and the tangent all pass through P; label it on the side they don't cross.
        label_side = UL if board.derivative > 0 else UR if board.derivative < 0 else UP
        point_label = self.label(board.point_label, POINT_COLOR).next_to(point, label_side, buff=0.15)
        self.show_caption("curve")
        self.play(Create(curve), FadeIn(curve_label), run_time=board.run_time("curve"))
        self.show_caption("point")
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

    def _build_secant_parts(self, h: ValueTracker):
        board, axes, fn = self.board, self.axes, self.fn

        def q_point():
            q_x = board.x0 + h.get_value()
            return axes.c2p(q_x, fn.f(q_x))

        secant = always_redraw(
            lambda: self._line_through_p(secant_slope(fn, board.x0, h.get_value()), SECANT_COLOR)
        )
        q_dot = always_redraw(lambda: Dot(q_point(), color=SECANT_COLOR).set_z_index(1))
        q_label = always_redraw(
            lambda: self.text("Q", SECANT_COLOR).next_to(q_point(), RIGHT, buff=0.15)
        )
        formula = self.label(board.secant_slope_label, SECANT_COLOR)
        self._place_panel(formula)
        readout = always_redraw(
            lambda: self.text(
                with_minus(f"h = {h.get_value():.2f}   "
                           f"Slope = {secant_slope(fn, board.x0, h.get_value()):.2f}"), WHITE
            ).next_to(formula, DOWN, aligned_edge=LEFT)
        )
        return secant, q_dot, q_label, VGroup(formula, readout)

    def _show_tangent(self, fade_out: VGroup, panel: VGroup) -> Line:
        board = self.board
        tangent = self._line_through_p(board.derivative, TANGENT_COLOR)
        limit_text = f"h → 0,  Slope → {with_minus(format_number(board.derivative))}"
        tangent_label = VGroup(
            self.label(board.tangent_label, TANGENT_COLOR), self.label(limit_text, TANGENT_COLOR)
        ).arrange(DOWN, aligned_edge=LEFT)
        tangent_label.next_to(panel, DOWN, aligned_edge=LEFT, buff=0.25)
        self.show_caption("tangent")
        self.play(Create(tangent), FadeOut(fade_out), run_time=board.run_time("tangent"))
        self.show_caption("tangent_label")
        self.play(Write(tangent_label), run_time=board.run_time("tangent_label"))
        return tangent

    def _measured_line(self, line: Line) -> LineEquation:
        """Slope and intercept measured back from the drawn line's endpoints."""
        x1, y1 = self.axes.p2c(line.get_start())[:2]
        x2, y2 = self.axes.p2c(line.get_end())[:2]
        slope = (y2 - y1) / (x2 - x1)
        return LineEquation(slope, y1 - slope * x1)

    def _record_measurements(self, point: Dot, tangent: Line, final_secant: Line, final_h: float) -> None:
        drawn_tangent = self._measured_line(tangent)
        px, py = self.axes.p2c(point.get_center())[:2]
        self.write_facts({
            "point_x": px,
            "point_y": py,
            "tangent_slope": drawn_tangent.slope,
            "tangent_intercept": drawn_tangent.intercept,
            "final_h": final_h,
            "final_secant_slope": self._measured_line(final_secant).slope,
        })
