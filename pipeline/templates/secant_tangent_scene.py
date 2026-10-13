"""Parameterized secant-to-tangent scene, adapted from animations/secant_tangent.

Run by the render stage via `python -m manim`. Reads its parameters from the
JSON file named in PIPELINE_SCENE_PARAMS and writes the values it actually drew
to PIPELINE_RENDER_FACTS, so the QA stage can compare them with the storyboard.
Supports landscape (16:9) and portrait (9:16). Uses only Text (no LaTeX).
"""

import os
from dataclasses import dataclass
from pathlib import Path

from manim import (
    BLUE, DOWN, GREEN, GREY_A, GREY_B, LEFT, ORANGE, RIGHT, UL, UP, UR, WHITE, YELLOW,
    Axes, Create, Dot, FadeIn, FadeOut, Line, Scene, Text, ValueTracker, VGroup, Write,
    always_redraw, config, smooth,
)

from pipeline.functions import (
    MINUS, LineEquation, clip_line_to_box, format_number, get_function, secant_slope,
)
from pipeline.schemas import RenderFacts, SceneParams
from pipeline.stages.render import FACTS_ENV, PARAMS_ENV

LINE_STROKE_WIDTH = 4
CURVE_LABEL_INSET = 0.4
CURVE_COLOR = BLUE
POINT_COLOR = YELLOW
SECANT_COLOR = ORANGE
TANGENT_COLOR = GREEN
CAPTION_COLOR = GREY_A


@dataclass(frozen=True)
class Layout:
    axes_width: float
    axes_height: float
    axes_bottom_buff: float
    title_font: int
    label_font: int
    caption_font: int
    side_margin: float  # text is scaled down to fit frame_width - 2 * side_margin


LAYOUTS = {
    "landscape": Layout(7.0, 6.0, 0.4, 36, 28, 28, 0.5),
    "portrait": Layout(4.0, 4.2, 0.5, 30, 22, 20, 0.2),
}


def _load_params() -> SceneParams:
    path = os.environ.get(PARAMS_ENV)
    if not path:
        raise RuntimeError(f"{PARAMS_ENV} is not set; run this scene through the pipeline")
    return SceneParams.model_validate_json(Path(path).read_text(encoding="utf-8"))


class SecantTangentTemplate(Scene):
    def __init__(self, **kwargs):
        # Match Manim's drawing area to the pixel aspect ratio (9:16 for portrait),
        # otherwise a portrait video would show a squeezed landscape frame.
        config.frame_width = config.frame_height * config.pixel_width / config.pixel_height
        super().__init__(**kwargs)

    def construct(self) -> None:
        self.board = _load_params().storyboard
        self.layout = LAYOUTS[self.board.format]
        self.portrait = self.board.format == "portrait"
        self.fn = get_function(self.board.function)
        self.labels: list[str] = []
        self.caption: Text | None = None

        self.title = self._fit(Text(self.board.topic, font_size=self.layout.title_font, color=WHITE))
        self.title.to_edge(UP, buff=0.3)
        self.caption_y = self.title.get_bottom()[1] - 0.35
        self.axes = self._build_axes()
        self._animate()

    # --- layout helpers -------------------------------------------------------

    def _fit(self, mobject):
        max_width = config.frame_width - 2 * self.layout.side_margin
        return mobject.scale_to_fit_width(max_width) if mobject.width > max_width else mobject

    def _text(self, text: str, color, font_size: int | None = None) -> Text:
        return Text(text, font_size=font_size or self.layout.label_font, color=color)

    def _show_caption(self, beat_name: str) -> None:
        """Swap the on-screen explanation instantly so beat timing is unchanged."""
        caption = self.board.beat(beat_name).caption
        if not caption:
            return
        if self.caption is not None:
            self.remove(self.caption)
        self.caption = self._fit(self._text(caption, CAPTION_COLOR, self.layout.caption_font))
        self.caption.move_to([0, self.caption_y, 0])
        self.add(self.caption)
        self.labels.append(caption)

    def _place_panel(self, mobject) -> None:
        if self.portrait:  # stacked under the caption, left-aligned
            mobject.next_to([0, self.caption_y - 0.25, 0], DOWN, buff=0.1)
            mobject.to_edge(LEFT, buff=self.layout.side_margin + 0.1)
        else:  # top-left corner, beside the axes
            mobject.to_corner(UL).shift(DOWN * 0.9)

    # --- scene ------------------------------------------------------------------

    def _animate(self) -> None:
        board = self.board
        self.play(Write(self.title), run_time=board.run_time("title"))
        self._show_caption("axes")
        self.play(Create(self.axes), run_time=board.run_time("axes"))
        point = self._show_curve_and_point()

        h = ValueTracker(board.h_start)
        secant, q_dot, q_label, panel = self._build_secant_parts(h)
        point.set_z_index(1)
        self._show_caption("secant")
        self.play(Create(secant), FadeIn(q_dot, q_label), FadeIn(panel), run_time=board.run_time("secant"))
        self._show_caption("secant_pause")
        self.wait(board.run_time("secant_pause"))

        self._show_caption("shrink")
        self.play(h.animate.set_value(board.h_end), run_time=board.run_time("shrink"), rate_func=smooth)
        self._show_caption("shrink_pause")
        self.wait(board.run_time("shrink_pause"))
        final_secant = secant.copy()

        tangent = self._show_tangent(VGroup(secant, q_dot, q_label), panel)
        self.wait(board.run_time("hold"))
        self._write_facts(point, tangent, final_secant, h.get_value())

    def _build_axes(self) -> Axes:
        spec, layout = self.board.axes, self.layout
        # Tick numbers stay off: Manim renders them with LaTeX.
        axes = Axes(
            x_range=(spec.x_min, spec.x_max, spec.x_step),
            y_range=(spec.y_min, spec.y_max, spec.y_step),
            x_length=layout.axes_width, y_length=layout.axes_height,
            axis_config={"color": GREY_B, "include_numbers": False}, tips=True,
        )
        return axes.to_edge(DOWN, buff=layout.axes_bottom_buff)

    def _show_curve_and_point(self) -> Dot:
        board, axes = self.board, self.axes
        curve = axes.plot(self.fn.f, x_range=(board.axes.x_min, board.axes.x_max), color=CURVE_COLOR)
        # Label the curve near whichever end is higher, on the inner side of the curve.
        right_end_higher = self.fn.f(board.axes.x_max) >= self.fn.f(board.axes.x_min)
        label_x = (board.axes.x_max - CURVE_LABEL_INSET if right_end_higher
                   else board.axes.x_min + CURVE_LABEL_INSET)
        curve_label = self._text(board.function_label, CURVE_COLOR)
        curve_label.next_to(axes.c2p(label_x, min(self.fn.f(label_x), board.axes.y_max)),
                            UL if right_end_higher else UR, buff=0.15)
        point = Dot(axes.c2p(board.x0, board.y0), color=POINT_COLOR)
        # Secants and the tangent all pass through P; label it on the side they don't cross.
        label_side = UL if board.derivative > 0 else UR if board.derivative < 0 else UP
        point_label = self._text(board.point_label, POINT_COLOR).next_to(point, label_side, buff=0.15)
        self.labels += [board.function_label, board.point_label]
        self._show_caption("curve")
        self.play(Create(curve), FadeIn(curve_label), run_time=board.run_time("curve"))
        self._show_caption("point")
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
            lambda: self._text("Q", SECANT_COLOR).next_to(q_point(), RIGHT, buff=0.15)
        )
        formula = self._text(board.secant_slope_label, SECANT_COLOR)
        self._place_panel(formula)
        readout = always_redraw(
            lambda: self._text(
                f"h = {h.get_value():.2f}   "
                f"Slope = {secant_slope(fn, board.x0, h.get_value()):.2f}".replace("-", MINUS), WHITE
            ).next_to(formula, DOWN, aligned_edge=LEFT)
        )
        self.labels.append(board.secant_slope_label)
        return secant, q_dot, q_label, VGroup(formula, readout)

    def _show_tangent(self, fade_out: VGroup, panel: VGroup) -> Line:
        board = self.board
        tangent = self._line_through_p(board.derivative, TANGENT_COLOR)
        limit_text = f"h → 0,  Slope → {format_number(board.derivative).replace('-', MINUS)}"
        tangent_label = VGroup(
            self._text(board.tangent_label, TANGENT_COLOR), self._text(limit_text, TANGENT_COLOR)
        ).arrange(DOWN, aligned_edge=LEFT)
        tangent_label.next_to(panel, DOWN, aligned_edge=LEFT, buff=0.25)
        self.labels += [board.tangent_label, limit_text]
        self._show_caption("tangent")
        self.play(Create(tangent), FadeOut(fade_out), run_time=board.run_time("tangent"))
        self._show_caption("tangent_label")
        self.play(Write(tangent_label), run_time=board.run_time("tangent_label"))
        return tangent

    def _measured_line(self, line: Line) -> LineEquation:
        """Slope and intercept measured back from the drawn line's endpoints."""
        x1, y1 = self.axes.p2c(line.get_start())[:2]
        x2, y2 = self.axes.p2c(line.get_end())[:2]
        slope = (y2 - y1) / (x2 - x1)
        return LineEquation(slope, y1 - slope * x1)

    def _write_facts(self, point: Dot, tangent: Line, final_secant: Line, final_h: float) -> None:
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
            labels=self.labels,
        )
        Path(path).write_text(facts.model_dump_json(indent=2), encoding="utf-8")
