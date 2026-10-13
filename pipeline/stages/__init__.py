"""The ordered list of pipeline stages and the files each one reads and writes."""

from pathlib import Path

from pipeline.runner import Stage
from pipeline.stages import package, plan, quality_check, render

FUNCTIONS_FILE = Path(__file__).resolve().parent.parent / "functions.py"

DEFAULT_STAGES: tuple[Stage, ...] = (
    Stage(
        name="plan",
        inputs=lambda p: (p.brief,),
        outputs=lambda p: (p.storyboard,),
        run=plan.run,
        validate=plan.validate,
    ),
    Stage(
        name="render",
        # The template imports pipeline.functions, so editing either must re-render.
        inputs=lambda p: (p.storyboard, render.TEMPLATE_FILE, FUNCTIONS_FILE),
        outputs=lambda p: (p.scene_params, p.video, p.render_facts, p.render_log),
        run=render.run,
        validate=render.validate,
    ),
    Stage(
        name="quality_check",
        inputs=lambda p: (p.video, p.render_facts, p.storyboard),
        outputs=lambda p: (p.qa_report,),
        run=quality_check.run,
        validate=quality_check.validate,
    ),
    Stage(
        name="package",
        inputs=lambda p: (p.storyboard, p.qa_report, p.video),
        outputs=lambda p: (p.preview,),
        run=package.run,
    ),
)
