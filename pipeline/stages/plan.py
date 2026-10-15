"""Plan stage: brief.json -> lesson_plan.json -> storyboard.json.

1. Lesson plan (what to teach): taken from the brief if it supplies one
   ({"format": ..., "lesson": {...}}), otherwise built deterministically by the
   visual named in the brief. Its claims and equations are verified here.
2. Storyboard (how to show it): built by the lesson's visualization from the
   verified lesson, then its on-screen math is checked too.
Both checks run before any rendering. No AI is involved yet.
"""

from pipeline.lesson import verify_lesson
from pipeline.paths import ProjectPaths
from pipeline.runner import StageError
from pipeline.schemas import STORYBOARD_ADAPTER, BriefError, LessonBrief, LessonPlan, load_brief
from pipeline.stages._io import read_model, write_model
from pipeline.visuals import VISUALS


def plan_lesson(brief) -> tuple[LessonPlan, str]:
    """(lesson plan, video format) for either kind of brief."""
    if isinstance(brief, LessonBrief):
        return brief.lesson, brief.format
    return VISUALS[brief.template].build_lesson(brief), brief.format


def _raise_on_failures(checks, what: str) -> None:
    failed = [f"{c.name}: {c.detail}" for c in checks if c.status != "pass"]
    if failed:
        raise StageError(f"{what} failed before rendering:\n  " + "\n  ".join(failed))


def verify_storyboard(storyboard) -> None:
    """Check the storyboard's on-screen math; raise StageError listing any failure."""
    _raise_on_failures(VISUALS[storyboard.template].check_math(storyboard), "Storyboard math check")


def build_storyboard(brief):
    """Storyboard for any supported brief, via its lesson plan."""
    lesson, video_format = plan_lesson(brief)
    return VISUALS[lesson.visualization.template].build_storyboard(lesson, video_format)


def run(paths: ProjectPaths) -> None:
    try:
        brief = load_brief(paths.brief)
    except BriefError as error:
        raise StageError(str(error)) from error
    lesson, video_format = plan_lesson(brief)
    _raise_on_failures(verify_lesson(lesson), "Lesson plan check")
    storyboard = VISUALS[lesson.visualization.template].build_storyboard(lesson, video_format)
    verify_storyboard(storyboard)
    write_model(paths.lesson_plan, lesson)
    write_model(paths.storyboard, storyboard)


def validate(paths: ProjectPaths) -> None:
    read_model(paths.lesson_plan, LessonPlan)
    read_model(paths.storyboard, STORYBOARD_ADAPTER)
