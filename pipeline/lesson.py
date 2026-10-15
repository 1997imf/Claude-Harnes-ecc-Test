"""Checks for lesson plans: is every claimed result true, and does it fit the visualization?

Schema validation (pipeline.schemas) catches malformed plans. These checks
catch well-formed plans that are mathematically wrong or that ask a template
to show something it cannot. They run before rendering and again during QA.
"""

from pipeline.arithmetic import evaluate_equation
from pipeline.functions import get_function, numeric_derivative
from pipeline.schemas import CheckResult, DerivativeClaim, LessonPlan, OddSumClaim, PythagoreanClaim
from pipeline.visuals import VISUALS

DERIVATIVE_TOLERANCE = 1e-9
NUMERIC_DERIVATIVE_TOLERANCE = 1e-6
# Checks the QA stage runs for every video, whatever its visualization.
GENERIC_CHECK_NAMES = frozenset(
    {"video_file", "video_decodes", "resolution", "duration", "frames_not_blank", "rendered_values"}
)
# Which visualization can show each kind of claim.
CLAIM_TEMPLATES = {"derivative": "secant_tangent", "pythagorean": "pythagoras", "odd_sum": "odd_sum"}


def _claim_error(claim) -> str | None:
    """Why the claim is false, or None if it is true."""
    if isinstance(claim, DerivativeClaim):
        fn = get_function(claim.function)
        exact, numeric = fn.derivative(claim.at), numeric_derivative(fn, claim.at)
        if abs(claim.value - exact) > DERIVATIVE_TOLERANCE or abs(numeric - exact) > NUMERIC_DERIVATIVE_TOLERANCE:
            return f"derivative of {claim.function} at {claim.at:g} is {exact:g}, not {claim.value:g}"
    elif isinstance(claim, PythagoreanClaim):
        if min(claim.a, claim.b, claim.c) <= 0 or claim.a ** 2 + claim.b ** 2 != claim.c ** 2:
            return f"{claim.a}² + {claim.b}² = {claim.a ** 2 + claim.b ** 2}, but {claim.c}² = {claim.c ** 2}"
    elif isinstance(claim, OddSumClaim):
        actual = sum(2 * k - 1 for k in range(1, claim.n + 1))
        if claim.n < 1 or actual != claim.total:
            return f"the first {claim.n} odd numbers add up to {actual}, not {claim.total}"
    return None


def _shows(claim, visualization) -> bool:
    """Does the visualization's example match this claim's values?"""
    if CLAIM_TEMPLATES[claim.kind] != visualization.template:
        return False
    if isinstance(claim, DerivativeClaim):
        return claim.function == visualization.function and claim.at == visualization.x0
    if isinstance(claim, PythagoreanClaim):
        return (claim.a, claim.b) == (visualization.a, visualization.b)
    return claim.n == visualization.n


def _equation_errors(lesson: LessonPlan) -> list[str]:
    errors = []
    for equation in lesson.equations:
        if equation.arithmetic is None:
            continue
        try:
            left, right = evaluate_equation(equation.arithmetic)
        except ValueError as error:
            errors.append(f"{equation.display!r}: {error}")
            continue
        if left != right:
            errors.append(f"{equation.display!r}: {equation.arithmetic} is false ({left} ≠ {right})")
    return errors


def verify_lesson(lesson: LessonPlan) -> list[CheckResult]:
    viz = lesson.visualization
    claim_errors = [e for e in (_claim_error(c) for c in lesson.results) if e]
    equation_errors = _equation_errors(lesson)
    mismatched = [c.kind for c in lesson.results if not _shows(c, viz)]
    known = GENERIC_CHECK_NAMES | VISUALS[viz.template].check_names
    unknown = sorted(set(lesson.required_checks) - known)
    checked_equations = sum(e.arithmetic is not None for e in lesson.equations)
    return [
        CheckResult.of("lesson_results", not claim_errors,
                       "; ".join(claim_errors) or f"all {len(lesson.results)} claimed results are true"),
        CheckResult.of("lesson_equations", not equation_errors,
                       "; ".join(equation_errors) or f"{checked_equations} arithmetic equation(s) checked exactly"),
        CheckResult.of("lesson_visualization", not mismatched,
                       f"claims not shown by the {viz.template} visualization: {mismatched}" if mismatched
                       else f"every claim is shown by the {viz.template} visualization"),
        CheckResult.of("lesson_required_checks", not unknown,
                       f"unknown for {viz.template}: {unknown}" if unknown
                       else f"{len(lesson.required_checks)} required checks exist for {viz.template}"),
    ]


def check_required(lesson: LessonPlan, checks: list[CheckResult]) -> CheckResult:
    """QA: the lesson is still valid and every check it requires actually ran and passed."""
    lesson_problems = [f"{c.name}: {c.detail}" for c in verify_lesson(lesson) if c.status != "pass"]
    status = {c.name: c.status for c in checks}
    not_run = [name for name in lesson.required_checks if name not in status]
    failed = [name for name in lesson.required_checks if status.get(name, "pass") != "pass"]
    problems = lesson_problems + ([f"required checks not run: {not_run}"] if not_run else []) \
        + ([f"required checks failed: {failed}"] if failed else [])
    return CheckResult.of(
        "lesson_plan", not problems,
        "; ".join(problems) or f"lesson verified; all {len(lesson.required_checks)} required checks ran and passed",
    )
