"""Tests for lesson plans: schema validation, math verification, compatibility, QA."""

import json
from fractions import Fraction

import pytest
from pydantic import ValidationError

from pipeline.arithmetic import evaluate_equation
from pipeline.lesson import check_required, verify_lesson
from pipeline.runner import StageError
from pipeline.schemas import (
    CheckResult, LessonPlan, OddSumBrief, PythagorasBrief, SecantBrief, load_brief,
)
from pipeline.stages.plan import run as plan_run
from pipeline.visuals import VISUALS
from tests.conftest import write_brief


def _lesson_dict(**changes) -> dict:
    brief = PythagorasBrief(template="pythagoras", topic="Pythagoras", a=3, b=4)
    data = VISUALS["pythagoras"].build_lesson(brief).model_dump(mode="json")
    return {**data, **changes}


def _failed(lesson: LessonPlan) -> dict[str, str]:
    return {c.name: c.detail for c in verify_lesson(lesson) if c.status != "pass"}


# --- arithmetic ----------------------------------------------------------------------

def test_arithmetic_is_exact():
    assert evaluate_equation("0.1 + 0.2 == 0.3") == (Fraction(3, 10), Fraction(3, 10))
    assert evaluate_equation("3**2 + 4**2 == 5**2") == (25, 25)


@pytest.mark.parametrize(
    "text, message",
    [
        ("x**2 == 4", "'Name' is not allowed"),
        ("__import__('os').system('ls') == 0", "'Call' is not allowed"),
        ("1 == 1 == 1", "exactly one '=='"),
        ("2 + 2", "exactly one '=='"),
        ("True == 1", "only numbers"),
        ("2 +", "not a valid arithmetic equation"),
        ("2**100 == 1", "exponents must be whole numbers up to"),
        ("1 / 0 == 1", "division by zero"),
    ],
)
def test_arithmetic_rejects_anything_but_plain_numbers(text, message):
    with pytest.raises(ValueError, match=message):
        evaluate_equation(text)


# --- schema validation -------------------------------------------------------------------

def test_deterministic_lesson_round_trips_through_json():
    data = _lesson_dict()

    assert LessonPlan.model_validate(json.loads(json.dumps(data))).model_dump(mode="json") == data


@pytest.mark.parametrize("missing", ["topic", "learning_objective", "audience", "results", "steps",
                                     "conclusion", "visualization", "required_checks"])
def test_missing_required_field_is_rejected(missing):
    data = {k: v for k, v in _lesson_dict().items() if k != missing}

    with pytest.raises(ValidationError, match=missing):
        LessonPlan.model_validate(data)


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"equations": [{"display": "x² = 4", "arithmetic": "x**2 == 4"}]}, "'Name' is not allowed"),
        ({"equations": [{"display": "", "arithmetic": "1 == 1"}]}, "at least 1 character"),
        ({"results": []}, "at least 1 item"),
        ({"results": [{"kind": "integral", "value": 1}]}, "does not match any of the expected tags"),
        ({"steps": ["only one step"]}, "at least 2 items"),
        ({"audience": "toddlers"}, "Input should be 'middle_school'"),
        ({"visualization": {"template": "spirograph"}}, "does not match any of the expected tags"),
        ({"visualization": {"template": "pythagoras", "a": 2, "b": 3}}, "not form a Pythagorean triple"),
        ({"results": [{"kind": "derivative", "function": "sin(x)", "at": 0, "value": 1}]},
         "Unsupported function"),
        ({"surprise": True}, "Extra inputs are not permitted"),
    ],
)
def test_malformed_lesson_is_rejected_by_the_schema(changes, message):
    with pytest.raises(ValidationError, match=message):
        LessonPlan.model_validate(_lesson_dict(**changes))


# --- mathematical verification -----------------------------------------------------------

@pytest.mark.parametrize(
    "brief",
    [
        SecantBrief(topic="t", function="x**3", x0=-1, h_start=1),
        PythagorasBrief(template="pythagoras", topic="t", a=5, b=12),
        OddSumBrief(template="odd_sum", topic="t", n=6),
    ],
    ids=lambda b: b.template,
)
def test_deterministic_lessons_for_every_visual_pass_all_checks(brief):
    assert _failed(VISUALS[brief.template].build_lesson(brief)) == {}


@pytest.mark.parametrize(
    "results, fragment",
    [
        ([{"kind": "pythagorean", "a": 3, "b": 4, "c": 6}], "but 6² = 36"),
        ([{"kind": "odd_sum", "n": 4, "total": 15}], "add up to 16, not 15"),
        ([{"kind": "derivative", "function": "x**2", "at": 1, "value": 3}], "is 2, not 3"),
    ],
)
def test_incorrect_results_are_caught(results, fragment):
    lesson = LessonPlan.model_validate(_lesson_dict(results=results))

    assert fragment in _failed(lesson)["lesson_results"]


def test_false_arithmetic_equation_is_caught():
    lesson = LessonPlan.model_validate(_lesson_dict(equations=[{"display": "9 + 16 = 26",
                                                                 "arithmetic": "9 + 16 == 26"}]))

    assert "is false (25 ≠ 26)" in _failed(lesson)["lesson_equations"]


@pytest.mark.parametrize(
    "changes, check",
    [
        # a derivative claim cannot be shown by the Pythagoras template
        ({"results": [{"kind": "derivative", "function": "x**2", "at": 1, "value": 2}]}, "lesson_visualization"),
        # a true triple, but not the one this visualization draws
        ({"results": [{"kind": "pythagorean", "a": 5, "b": 12, "c": 13}]}, "lesson_visualization"),
        # a check that the Pythagoras visualization does not have
        ({"required_checks": ["derivative", "rendered_values"]}, "lesson_required_checks"),
    ],
)
def test_incompatible_visualization_is_caught(changes, check):
    assert check in _failed(LessonPlan.model_validate(_lesson_dict(**changes)))


# --- plan stage and QA ----------------------------------------------------------------------

def test_classic_brief_produces_a_lesson_plan_file(example_project):
    plan_run(example_project)

    lesson = LessonPlan.model_validate_json(example_project.lesson_plan.read_text())
    assert lesson.visualization.template == "secant_tangent"
    assert lesson.results[0].value == 2.0


def test_ready_made_lesson_brief_is_planned_and_rendered_from_its_lesson(tmp_path):
    paths = write_brief(tmp_path / "p", {"format": "portrait", "lesson": _lesson_dict(topic="Hand-written lesson")})

    plan_run(paths)

    assert LessonPlan.model_validate_json(paths.lesson_plan.read_text()).topic == "Hand-written lesson"
    assert json.loads(paths.storyboard.read_text())["format"] == "portrait"


def test_wrong_lesson_brief_stops_before_rendering(tmp_path):
    wrong = _lesson_dict(results=[{"kind": "pythagorean", "a": 3, "b": 4, "c": 6}])
    paths = write_brief(tmp_path / "p", {"lesson": wrong})

    with pytest.raises(StageError, match="Lesson plan check failed before rendering"):
        plan_run(paths)
    assert not paths.storyboard.exists()


def test_lesson_brief_is_detected_by_load_brief(tmp_path):
    path = write_brief(tmp_path / "p", {"lesson": _lesson_dict()}).brief

    assert load_brief(path).lesson.visualization.template == "pythagoras"


def _qa(names, status="pass"):
    return [CheckResult(name=n, status=status, detail="") for n in names]


def test_qa_lesson_check_requires_every_required_check_to_run_and_pass():
    lesson = LessonPlan.model_validate(_lesson_dict())
    required = list(lesson.required_checks)

    assert check_required(lesson, _qa(required)).status == "pass"
    not_run = check_required(lesson, _qa(required[1:]))
    assert not_run.status == "fail" and "not run" in not_run.detail
    failed = check_required(lesson, _qa(required[:-1]) + _qa(required[-1:], "fail"))
    assert failed.status == "fail" and "failed" in failed.detail


def test_each_visual_declares_exactly_the_checks_it_runs():
    for brief in (SecantBrief(topic="t", function="x**2", x0=1, h_start=1.5),
                  PythagorasBrief(template="pythagoras", topic="t", a=3, b=4),
                  OddSumBrief(template="odd_sum", topic="t", n=3)):
        visual = VISUALS[brief.template]
        storyboard = visual.build_storyboard(visual.build_lesson(brief), "landscape")
        assert {c.name for c in visual.check_math(storyboard)} == visual.check_names


def test_display_only_equations_are_not_counted_as_checked_and_bad_arithmetic_fails():
    lesson = LessonPlan.model_validate(_lesson_dict(equations=[
        {"display": "a² + b² = c²"},  # shown only; nothing to evaluate
        {"display": "nonsense", "arithmetic": "1 / 0 == 1"},  # parses, but cannot be evaluated
    ]))

    detail = _failed(lesson)["lesson_equations"]
    assert "division by zero" in detail and "a² + b² = c²" not in detail

    ok = LessonPlan.model_validate(_lesson_dict(equations=[{"display": "a² + b² = c²"}]))
    passed = {c.name: c.detail for c in verify_lesson(ok)}
    assert passed["lesson_equations"] == "0 arithmetic equation(s) checked exactly"
