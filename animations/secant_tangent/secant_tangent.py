"""Secant-to-tangent animation for f(x) = x^2.

Draw the parabola and P = (1, 1), add Q = (1 + h, (1 + h)^2) with the secant
line PQ, shrink h toward 0, then reveal the tangent line y = 2x - 1.
Uses only `Text` (no MathTex/Tex), so no LaTeX installation is required.

Render (low quality, from this folder):
    .venv/bin/manim -pql secant_tangent.py SecantTangent
"""

from manim import (
    BLUE,
    DOWN,
    DR,
    GREEN,
    GREY_B,
    LEFT,
    ORANGE,
    RIGHT,
    UL,
    UP,
    WHITE,
    YELLOW,
    Axes,
    Create,
    Dot,
    FadeIn,
    FadeOut,
    Line,
    Scene,
    Text,
    ValueTracker,
    VGroup,
    Write,
    always_redraw,
    smooth,
)

X_RANGE = (-1.0, 3.0, 1.0)
Y_RANGE = (-1.0, 9.0, 1.0)
AXES_WIDTH = 7.0
AXES_HEIGHT = 6.0

POINT_X = 1.0
CURVE_LABEL_X = 2.6
LABEL_FONT_SIZE = 28
TITLE_FONT_SIZE = 36

CURVE_COLOR = BLUE
POINT_COLOR = YELLOW
SECANT_COLOR = ORANGE
TANGENT_COLOR = GREEN

H_START = 1.5
H_END = 0.01  # stop just short of 0: the slope formula divides by h
SHRINK_RUN_TIME = 6.0
LINE_STROKE_WIDTH = 4


def f(x: float) -> float:
    """The function whose secant and tangent lines are animated."""
    return x**2


def secant_slope(x: float, h: float) -> float:
    """Slope of the line through (x, f(x)) and (x + h, f(x + h)); equals 2x + h for x^2."""
    return (f(x + h) - f(x)) / h


def line_x_range(x0: float, y0: float, slope: float) -> tuple[float, float]:
    """x-interval where the line through (x0, y0) stays inside the axes' x and y ranges."""
    x_min, x_max = X_RANGE[:2]
    y_min, y_max = Y_RANGE[:2]
    if slope == 0:
        return x_min, x_max
    x_at_y_min = x0 + (y_min - y0) / slope
    x_at_y_max = x0 + (y_max - y0) / slope
    low, high = sorted((x_at_y_min, x_at_y_max))
    return max(x_min, low), min(x_max, high)


class SecantTangent(Scene):
    """The secant through P and Q on f(x) = x^2 turns into the tangent at P as h -> 0."""

    def construct(self) -> None:
        title = Text("Secant → Tangent", font_size=TITLE_FONT_SIZE, color=WHITE)
        title.to_edge(UP)

        axes = self._build_axes()
        curve = axes.plot(f, x_range=X_RANGE[:2], color=CURVE_COLOR)
        curve_label = Text("f(x) = x²", font_size=LABEL_FONT_SIZE, color=CURVE_COLOR)
        curve_label.next_to(axes.c2p(CURVE_LABEL_X, f(CURVE_LABEL_X)), UL, buff=0.15)

        point = Dot(axes.c2p(POINT_X, f(POINT_X)), color=POINT_COLOR)
        point_label = Text("P (1, 1)", font_size=LABEL_FONT_SIZE, color=POINT_COLOR)
        point_label.next_to(point, DR, buff=0.15)

        self.play(Write(title))
        self.play(Create(axes))
        self.play(Create(curve), FadeIn(curve_label))
        self.play(FadeIn(point, scale=1.5), FadeIn(point_label))
        self.wait(1)

        h = ValueTracker(H_START)
        secant, q_dot, q_label, slope_panel = self._build_secant_parts(axes, h)
        point.set_z_index(1)
        self.play(Create(secant), FadeIn(q_dot, q_label), FadeIn(slope_panel))
        self.wait(1)

        self.play(
            h.animate.set_value(H_END),
            run_time=SHRINK_RUN_TIME,
            rate_func=smooth,
        )
        self.wait(1)

        self._show_tangent(axes, fade_out=VGroup(secant, q_dot, q_label))
        self.wait(2)

    def _line_through(self, axes: Axes, slope: float, color) -> Line:
        """Line through P with the given slope, clipped to the visible axes."""
        y0 = f(POINT_X)
        x_low, x_high = line_x_range(POINT_X, y0, slope)
        return Line(
            axes.c2p(x_low, y0 + slope * (x_low - POINT_X)),
            axes.c2p(x_high, y0 + slope * (x_high - POINT_X)),
            color=color,
            stroke_width=LINE_STROKE_WIDTH,
        )

    def _build_secant_parts(self, axes: Axes, h: ValueTracker):
        """Secant line, point Q, its label, and the slope readout, all driven by h."""
        def q_point():
            q_x = POINT_X + h.get_value()
            return axes.c2p(q_x, f(q_x))

        secant = always_redraw(
            lambda: self._line_through(axes, secant_slope(POINT_X, h.get_value()), SECANT_COLOR)
        )
        q_dot = always_redraw(lambda: Dot(q_point(), color=SECANT_COLOR).set_z_index(1))
        q_label = always_redraw(
            lambda: Text("Q", font_size=LABEL_FONT_SIZE, color=SECANT_COLOR).next_to(
                q_point(), RIGHT, buff=0.15
            )
        )

        formula = Text("Slope = 2 + h", font_size=LABEL_FONT_SIZE, color=SECANT_COLOR)
        formula.to_corner(UL).shift(DOWN * 0.9)
        readout = always_redraw(
            lambda: Text(
                f"h = {h.get_value():.2f}   Slope = {secant_slope(POINT_X, h.get_value()):.2f}",
                font_size=LABEL_FONT_SIZE,
                color=WHITE,
            ).next_to(formula, DOWN, aligned_edge=LEFT)
        )
        return secant, q_dot, q_label, VGroup(formula, readout)

    def _show_tangent(self, axes: Axes, fade_out: VGroup) -> None:
        """Replace the nearly-tangent secant with the exact tangent y = 2x - 1."""
        tangent_slope = 2 * POINT_X
        tangent = self._line_through(axes, tangent_slope, TANGENT_COLOR)
        # Two short lines so the label stays left of the y-axis.
        tangent_label = VGroup(
            Text("Tangent: y = 2x − 1", font_size=LABEL_FONT_SIZE, color=TANGENT_COLOR),
            Text("h → 0,  Slope → 2", font_size=LABEL_FONT_SIZE, color=TANGENT_COLOR),
        ).arrange(DOWN, aligned_edge=LEFT)
        tangent_label.to_corner(UL).shift(DOWN * 2.1)

        self.play(Create(tangent), FadeOut(fade_out))
        self.play(Write(tangent_label))

    def _build_axes(self) -> Axes:
        # Tick numbers stay off: Manim renders them as DecimalNumber, which needs LaTeX.
        axes = Axes(
            x_range=X_RANGE,
            y_range=Y_RANGE,
            x_length=AXES_WIDTH,
            y_length=AXES_HEIGHT,
            axis_config={"color": GREY_B, "include_numbers": False},
            tips=True,
        )
        return axes.to_edge(DOWN, buff=0.4)
