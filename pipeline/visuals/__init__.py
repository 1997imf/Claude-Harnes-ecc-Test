"""Registry of supported visualization types.

Each visual pairs reviewed planning/QA code with one reviewed Manim template.
The brief's `template` field selects the visual; nothing is AI-generated.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any, NamedTuple

from pipeline.schemas import CheckResult
from pipeline.visuals import odd_sum, pythagoras, secant_tangent

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


class Visual(NamedTuple):
    build_lesson: Callable[[Any], Any]  # classic brief -> LessonPlan (deterministic planner)
    build_storyboard: Callable[[Any, str], Any]  # (LessonPlan, video format) -> storyboard
    check_math: Callable[[Any], list[CheckResult]]  # run before rendering and again in QA
    expected_values: Callable[[Any], dict[str, float]]  # what the template must measurably draw
    expected_labels: Callable[[Any], set[str]]  # text that must appear (captions are added by QA)
    check_names: frozenset[str]  # names check_math reports; lesson plans may require them
    template_file: Path
    scene_class: str


def _visual(module, template_name: str, scene_class: str) -> Visual:
    return Visual(module.build_lesson, module.build_storyboard, module.check_math, module.expected_values,
                  module.expected_labels, module.CHECK_NAMES, TEMPLATES_DIR / template_name, scene_class)


VISUALS: dict[str, Visual] = {
    "secant_tangent": _visual(secant_tangent, "secant_tangent_scene.py", "SecantTangentTemplate"),
    "pythagoras": _visual(pythagoras, "pythagoras_scene.py", "PythagorasTemplate"),
    "odd_sum": _visual(odd_sum, "odd_sum_scene.py", "OddSumTemplate"),
}

# Helper module shared by every template; editing it must re-render all videos.
TEMPLATE_FILES = tuple(v.template_file for v in VISUALS.values()) + (TEMPLATES_DIR / "_base.py",)
