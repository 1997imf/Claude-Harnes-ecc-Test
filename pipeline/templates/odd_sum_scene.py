"""Sum of odd numbers scene: L-shaped layers of 1, 3, 5, ... unit cells build an
n × n square, with the running sum shown after each layer.

Measured facts (cells per layer, total cells, final square size) are counted
from the cells actually drawn.
"""

from manim import (
    BLUE, GREEN, ORANGE, PINK, PURPLE, RED, TEAL, WHITE, YELLOW,
    Create, FadeIn, Square, SurroundingRectangle, VGroup,
)

from pipeline.templates._base import PipelineScene

LAYER_COLORS = (BLUE, TEAL, GREEN, YELLOW, ORANGE, RED, PURPLE, PINK)
FIGURE_TOP_GAP = 1.1  # room under the caption for the running-sum label
CELL_FILL = 0.92  # cell size relative to grid spacing (leaves a visible gap)
CELL_OPACITY = 0.8
SUM_LABEL_OFFSET = 0.6


class OddSumTemplate(PipelineScene):
    def construct(self) -> None:
        board = self.setup_board()
        n = board.n
        cx, cy, width, height = self.content_box(self.caption_y - FIGURE_TOP_GAP)
        self.spacing = min(width, height) / n
        self.corner = (cx - self.spacing * n / 2, cy - self.spacing * n / 2)

        self.play_title()
        layers = []
        sum_label = None
        for k in range(1, n + 1):
            beat = f"layer_{k}"
            self.show_caption(beat)
            if sum_label is not None:
                self.remove(sum_label)
            sum_label = self.fit(self.label(board.sum_labels[k - 1], WHITE))
            sum_label.move_to([0, self.caption_y - SUM_LABEL_OFFSET, 0])
            self.add(sum_label)
            layer = self._layer(k)
            layers.append(layer)
            self.play(FadeIn(layer, lag_ratio=0.15), run_time=board.run_time(beat))

        self.show_caption("result")
        outline = SurroundingRectangle(VGroup(*layers), color=WHITE, buff=0.05)
        self.play(Create(outline), run_time=board.run_time("result"))
        self.show_caption("hold")
        self.wait(board.run_time("hold"))
        self._record_measurements(layers)

    def _cell(self, row: int, col: int, color) -> Square:
        x0, y0 = self.corner
        cell = Square(side_length=self.spacing * CELL_FILL, color=color, fill_color=color,
                      fill_opacity=CELL_OPACITY, stroke_width=1)
        return cell.move_to([x0 + (col + 0.5) * self.spacing, y0 + (row + 0.5) * self.spacing, 0])

    def _layer(self, k: int) -> VGroup:
        """Cells with max(row, col) == k - 1: an L of 2k - 1 cells around the (k-1)² square."""
        color = LAYER_COLORS[(k - 1) % len(LAYER_COLORS)]
        edge = k - 1
        cells = [(row, col) for row in range(k) for col in range(k) if max(row, col) == edge]
        return VGroup(*(self._cell(row, col, color) for row, col in cells))

    def _record_measurements(self, layers: list[VGroup]) -> None:
        values = {f"layer_{k}_cells": len(layer) for k, layer in enumerate(layers, start=1)}
        centers = [cell.get_center() for layer in layers for cell in layer]
        xs = [c[0] for c in centers]
        ys = [c[1] for c in centers]
        values["total_cells"] = len(centers)
        values["square_width_cells"] = round((max(xs) - min(xs)) / self.spacing) + 1
        values["square_height_cells"] = round((max(ys) - min(ys)) / self.spacing) + 1
        self.write_facts(values)
