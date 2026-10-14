"""Shared base for the reviewed Manim templates (portrait/landscape, title, captions, facts).

Templates read their storyboard from PIPELINE_SCENE_PARAMS and write what they
actually drew (measured values + every label) to PIPELINE_RENDER_FACTS, which
the QA stage compares with the storyboard. Uses only Text (no LaTeX).
"""

import os
from dataclasses import dataclass
from pathlib import Path

from manim import GREY_A, UP, WHITE, Scene, Text, Write, config

from pipeline.schemas import RenderFacts, SceneParams
from pipeline.stages.render import FACTS_ENV, PARAMS_ENV

CAPTION_COLOR = GREY_A
CAPTION_GAP = 0.35  # between title and caption
BOTTOM_MARGIN = 0.3


@dataclass(frozen=True)
class TextLayout:
    title_font: int
    label_font: int
    caption_font: int
    side_margin: float  # text is scaled down to fit frame_width - 2 * side_margin


TEXT_LAYOUTS = {
    "landscape": TextLayout(title_font=36, label_font=28, caption_font=28, side_margin=0.5),
    "portrait": TextLayout(title_font=30, label_font=22, caption_font=20, side_margin=0.2),
}


def load_params() -> SceneParams:
    path = os.environ.get(PARAMS_ENV)
    if not path:
        raise RuntimeError(f"{PARAMS_ENV} is not set; run this scene through the pipeline")
    return SceneParams.model_validate_json(Path(path).read_text(encoding="utf-8"))


class PipelineScene(Scene):
    def __init__(self, **kwargs):
        # Match Manim's drawing area to the pixel aspect ratio (9:16 for portrait),
        # otherwise a portrait video would show a squeezed landscape frame.
        config.frame_width = config.frame_height * config.pixel_width / config.pixel_height
        super().__init__(**kwargs)

    def setup_board(self):
        """Load the storyboard and lay out the title; returns the storyboard."""
        self.board = load_params().storyboard
        self.text_layout = TEXT_LAYOUTS[self.board.format]
        self.portrait = self.board.format == "portrait"
        self.labels: list[str] = []
        self.caption: Text | None = None
        self.title = self.fit(self.text(self.board.topic, WHITE, self.text_layout.title_font))
        self.title.to_edge(UP, buff=0.3)
        self.caption_y = self.title.get_bottom()[1] - CAPTION_GAP
        return self.board

    def play_title(self) -> None:
        self.play(Write(self.title), run_time=self.board.run_time("title"))

    def fit(self, mobject, max_width: float | None = None):
        limit = max_width or config.frame_width - 2 * self.text_layout.side_margin
        return mobject.scale_to_fit_width(limit) if mobject.width > limit else mobject

    def text(self, text: str, color, font_size: int | None = None) -> Text:
        return Text(text, font_size=font_size or self.text_layout.label_font, color=color)

    def label(self, text: str, color, font_size: int | None = None) -> Text:
        """A Text that QA should find on screen."""
        self.labels.append(text)
        return self.text(text, color, font_size)

    def show_caption(self, beat_name: str) -> None:
        """Swap the on-screen explanation instantly so beat timing is unchanged."""
        caption = self.board.beat(beat_name).caption
        if not caption:
            return
        if self.caption is not None:
            self.remove(self.caption)
        self.caption = self.fit(self.label(caption, CAPTION_COLOR, self.text_layout.caption_font))
        self.caption.move_to([0, self.caption_y, 0])
        self.add(self.caption)

    def content_box(self, top: float) -> tuple[float, float, float, float]:
        """(center_x, center_y, width, height) of the free area below `top`."""
        bottom = -config.frame_height / 2 + BOTTOM_MARGIN
        width = config.frame_width - 2 * self.text_layout.side_margin
        return 0.0, (top + bottom) / 2, width, top - bottom

    def write_facts(self, values: dict[str, float]) -> None:
        path = os.environ.get(FACTS_ENV)
        if path:
            facts = RenderFacts(values={k: float(v) for k, v in values.items()}, labels=self.labels)
            Path(path).write_text(facts.model_dump_json(indent=2), encoding="utf-8")
