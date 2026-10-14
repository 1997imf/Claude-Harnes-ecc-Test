"""Plan stage: brief.json -> storyboard.json.

Deterministic (no AI): the brief's `template` picks a reviewed visual, which
builds the storyboard from computed values only. Its math claims are checked
here, before any rendering happens.
"""

from pipeline.paths import ProjectPaths
from pipeline.runner import StageError
from pipeline.schemas import STORYBOARD_ADAPTER, BriefError, load_brief
from pipeline.stages._io import read_model, write_model
from pipeline.visuals import VISUALS


def build_storyboard(brief):
    """Storyboard for any supported brief, built by the brief's visual."""
    return VISUALS[brief.template].build_storyboard(brief)


def verify_storyboard(storyboard) -> None:
    """Check the math claims before rendering; raise StageError listing any failure."""
    checks = VISUALS[storyboard.template].check_math(storyboard)
    failed = [f"{c.name}: {c.detail}" for c in checks if c.status != "pass"]
    if failed:
        raise StageError("Storyboard math check failed before rendering:\n  " + "\n  ".join(failed))


def run(paths: ProjectPaths) -> None:
    try:
        brief = load_brief(paths.brief)
    except BriefError as error:
        raise StageError(str(error)) from error
    storyboard = build_storyboard(brief)
    verify_storyboard(storyboard)
    write_model(paths.storyboard, storyboard)


def validate(paths: ProjectPaths) -> None:
    read_model(paths.storyboard, STORYBOARD_ADAPTER)
