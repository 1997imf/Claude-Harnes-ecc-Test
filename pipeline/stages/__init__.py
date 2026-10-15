"""The ordered list of pipeline stages and the files each one reads and writes."""

from pathlib import Path

from pipeline import visuals
from pipeline.runner import Stage
from pipeline.stages import package, plan, quality_check, render
from pipeline.visuals import TEMPLATE_FILES

FUNCTIONS_FILE = Path(__file__).resolve().parent.parent / "functions.py"
SCHEMAS_FILE = Path(__file__).resolve().parent.parent / "schemas.py"
# Planning and math checks: every visual type plus the lesson-plan checks.
VISUAL_FILES = tuple(sorted(Path(visuals.__file__).resolve().parent.glob("*.py")))
LESSON_FILES = tuple(Path(__file__).resolve().parent.parent / name for name in ("lesson.py", "arithmetic.py"))


def _source(module) -> Path:
    """A stage's own code is one of its inputs: editing it must rerun the stage."""
    return Path(module.__file__).resolve()


DEFAULT_STAGES: tuple[Stage, ...] = (
    Stage(
        name="plan",
        inputs=lambda p: (p.brief, _source(plan), FUNCTIONS_FILE, SCHEMAS_FILE, *VISUAL_FILES, *LESSON_FILES),
        outputs=lambda p: (p.lesson_plan, p.storyboard),
        run=plan.run,
        validate=plan.validate,
    ),
    Stage(
        name="render",
        # Templates import pipeline.functions, so editing it must re-render too.
        inputs=lambda p: (p.storyboard, *TEMPLATE_FILES, FUNCTIONS_FILE, _source(render)),
        outputs=lambda p: (p.scene_params, p.video, p.render_facts, p.render_log),
        run=render.run,
        validate=render.validate,
    ),
    Stage(
        name="quality_check",
        inputs=lambda p: (p.video, p.render_facts, p.storyboard, p.lesson_plan, _source(quality_check),
                          *VISUAL_FILES, *LESSON_FILES),
        outputs=lambda p: (p.qa_report,),
        run=quality_check.run,
        validate=quality_check.validate,
    ),
    Stage(
        name="package",
        inputs=lambda p: (p.storyboard, p.lesson_plan, p.qa_report, p.video, _source(package)),
        outputs=lambda p: (p.metadata, p.preview),
        run=package.run,
    ),
)
