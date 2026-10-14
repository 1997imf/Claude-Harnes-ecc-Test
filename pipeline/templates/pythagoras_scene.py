"""Pythagorean theorem scene: squares on each side of a right triangle, drawn as
unit-cell grids, so the areas a², b², c² can be counted.

Measured facts (side lengths, right angle, square areas, grid cell counts) are
computed back from the drawn shapes, not copied from the storyboard.
"""

import math

import numpy as np
from manim import (
    BLUE, GREEN, ORANGE, RIGHT, WHITE, Create, FadeIn, Line, Polygon, VGroup, Write,
)

from pipeline.templates._base import PipelineScene

FIGURE_TOP_GAP = 1.5  # room under the caption for the equation and the side-length legend
FIGURE_FILL_OPACITY = 0.35
GRID_STROKE_WIDTH = 1
EDGE_STROKE_WIDTH = 4
LEGEND_OFFSET = 1.1  # side-length legend, below the equation line
SIDE_COLORS = {"a": BLUE, "b": GREEN, "c": ORANGE}


def _shoelace_area(points: np.ndarray) -> float:
    x, y = points[:, 0], points[:, 1]
    return abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))) / 2


class PythagorasTemplate(PipelineScene):
    def construct(self) -> None:
        board = self.setup_board()
        a, b = board.a, board.b
        top = self.caption_y - FIGURE_TOP_GAP
        cx, cy, width, height = self.content_box(top)
        # Bounding box of triangle + three squares, in triangle units.
        x_min, x_max, y_min, y_max = -b, a + b, -a, a + b
        self.unit = min(width / (x_max - x_min), height / (y_max - y_min))
        self.origin = np.array([cx - self.unit * (x_min + x_max) / 2, cy - self.unit * (y_min + y_max) / 2, 0])

        self.play_title()
        triangle = self._show_triangle()
        squares = {
            "a": self._show_square("square_a", (0, 0), (a, 0), (0, -a), a, SIDE_COLORS["a"]),
            "b": self._show_square("square_b", (0, 0), (0, b), (-b, 0), b, SIDE_COLORS["b"]),
            "c": self._show_square("square_c", (a, 0), (-a, b), (b, a), board.c, SIDE_COLORS["c"]),
        }
        self.show_caption("equation")
        equation = self.label(board.equation_label, WHITE)
        equation.move_to([0, self.caption_y - 0.6, 0])
        self.play(Write(equation), run_time=board.run_time("equation"))
        self.show_caption("hold")
        self.wait(board.run_time("hold"))
        self._record_measurements(triangle, squares)

    def p(self, x: float, y: float) -> np.ndarray:
        """Triangle units -> scene coordinates."""
        return self.origin + self.unit * np.array([x, y, 0])

    def to_units(self, point: np.ndarray) -> np.ndarray:
        return (point - self.origin)[:2] / self.unit

    def _show_triangle(self) -> Polygon:
        board = self.board
        a, b = board.a, board.b
        triangle = Polygon(self.p(0, 0), self.p(a, 0), self.p(0, b), color=WHITE, stroke_width=EDGE_STROKE_WIDTH)
        marker_size = min(a, b) * 0.15
        right_angle = VGroup(
            Line(self.p(marker_size, 0), self.p(marker_size, marker_size), color=WHITE),
            Line(self.p(0, marker_size), self.p(marker_size, marker_size), color=WHITE),
        )
        # Side lengths as a colour-coded legend: labels inside a thin triangle (e.g. 5-12-13)
        # would overlap. Colours match the squares drawn on each side.
        labels = VGroup(*(
            self.label(f"{side} = {length}", SIDE_COLORS[side])
            for side, length in (("a", a), ("b", b), ("c", board.c))
        )).arrange(RIGHT, buff=0.4)
        labels.move_to([0, self.caption_y - LEGEND_OFFSET, 0])
        self.show_caption("triangle")
        self.play(Create(triangle), Create(right_angle), FadeIn(labels), run_time=board.run_time("triangle"))
        return triangle

    def _show_square(self, beat: str, corner, along, outward, side: int, color) -> dict:
        """Square with corner + along + outward edges, split into side × side unit cells."""
        c0, u, v = np.array(corner, float), np.array(along, float), np.array(outward, float)
        square = Polygon(*(self.p(*pt) for pt in (c0, c0 + u, c0 + u + v, c0 + v)),
                         color=color, fill_color=color, fill_opacity=FIGURE_FILL_OPACITY,
                         stroke_width=EDGE_STROKE_WIDTH)
        lines_u = [Line(self.p(*(c0 + u * i / side)), self.p(*(c0 + u * i / side + v)),
                        color=color, stroke_width=GRID_STROKE_WIDTH) for i in range(1, side)]
        lines_v = [Line(self.p(*(c0 + v * i / side)), self.p(*(c0 + v * i / side + u)),
                        color=color, stroke_width=GRID_STROKE_WIDTH) for i in range(1, side)]
        area_label = self.label(str(side * side), WHITE).move_to(self.p(*(c0 + (u + v) / 2)))
        self.show_caption(beat)
        self.play(FadeIn(square), Create(VGroup(*lines_u, *lines_v)), FadeIn(area_label),
                  run_time=self.board.run_time(beat))
        return {"square": square, "cells": (len(lines_u) + 1) * (len(lines_v) + 1)}

    def _record_measurements(self, triangle: Polygon, squares: dict) -> None:
        right, end_a, end_b = (self.to_units(v) for v in triangle.get_vertices())
        leg_a, leg_b = end_a - right, end_b - right
        cosine = float(np.dot(leg_a, leg_b) / (np.linalg.norm(leg_a) * np.linalg.norm(leg_b)))
        values = {
            "leg_a": float(np.linalg.norm(leg_a)),
            "leg_b": float(np.linalg.norm(leg_b)),
            "hypotenuse": float(np.linalg.norm(end_b - end_a)),
            "right_angle_deg": math.degrees(math.acos(max(-1.0, min(1.0, cosine)))),
        }
        for name, drawn in squares.items():
            corners = np.array([self.to_units(v) for v in drawn["square"].get_vertices()])
            values[f"area_{name}"] = _shoelace_area(corners)
            values[f"cells_{name}"] = drawn["cells"]
        self.write_facts(values)
