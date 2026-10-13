"""The ordered list of pipeline stages and the files each one reads and writes."""

from pathlib import Path

from pipeline.runner import Stage
from pipeline.stages import package, plan, quality_check, render

FUNCTIONS_FILE = Path(__file__).resolve().parent.parent / "functions.py"


def _source(module) -> Path:
    """A stage's own code is one of its inputs: editing it must rerun the stage."""
    return Path(module.__file__).resolve()


DEFAULT_STAGES: tuple[Stage, ...] = (
    Stage(
        name="plan",
        inputs=lambda p: (p.brief, _source(plan), FUNCTIONS_FILE),
        outputs=lambda p: (p.storyboard,),
        run=plan.run,
        validate=plan.validate,
    ),
    Stage(
        name="render",
        # The template imports pipeline.functions, so editing either must re-render.
        inputs=lambda p: (p.storyboard, render.TEMPLATE_FILE, FUNCTIONS_FILE, _source(render)),
        outputs=lambda p: (p.scene_params, p.video, p.render_facts, p.render_log),
        run=render.run,
        validate=render.validate,
    ),
    Stage(
        name="quality_check",
        inputs=lambda p: (p.video, p.render_facts, p.storyboard, _source(quality_check)),
        outputs=lambda p: (p.qa_report,),
        run=quality_check.run,
        validate=quality_check.validate,
    ),
    Stage(
        name="package",
        inputs=lambda p: (p.storyboard, p.qa_report, p.video, _source(package)),
        outputs=lambda p: (p.metadata, p.preview),
        run=package.run,
    ),
)
