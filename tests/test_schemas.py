"""Tests for brief validation and its user-facing error messages."""

import json

import pytest

from pipeline.schemas import SecantBrief, BriefError, load_brief

VALID_BRIEF = {
    "topic": "Derivative as the limit of secants",
    "function": "x**2",
    "x0": 1,
    "h_start": 1.5,
}


def _brief_with(**changes):
    return {**VALID_BRIEF, **changes}


def _write(tmp_path, content):
    path = tmp_path / "brief.json"
    path.write_text(content if isinstance(content, str) else json.dumps(content))
    return path


def test_valid_brief_is_accepted_and_normalized():
    brief = SecantBrief.model_validate(_brief_with(function=" x ** 2 ", topic="  Secants  "))

    assert brief.function == "x**2"
    assert brief.topic == "Secants"
    assert brief.x0 == 1.0
    assert brief.h_start == 1.5


@pytest.mark.parametrize("missing", ["topic", "function", "x0", "h_start"])
def test_missing_required_field_is_rejected(missing):
    data = {k: v for k, v in VALID_BRIEF.items() if k != missing}

    with pytest.raises(ValueError, match=missing):
        SecantBrief.model_validate(data)


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"function": "x**4"}, "Unsupported function"),
        ({"function": "__import__('os')"}, "Unsupported function"),
        ({"x0": 10}, "less than or equal to 3"),
        ({"x0": True}, "must be a number"),
        ({"x0": "1"}, "must be a number"),
        ({"h_start": 0}, "greater than 0.01"),
        ({"h_start": -1}, "greater than 0.01"),
        ({"h_start": 5}, "less than or equal to 3"),
        ({"topic": "   "}, "topic must not be empty"),
        ({"surprise": 1}, "Extra inputs are not permitted"),
    ],
)
def test_invalid_values_are_rejected_with_clear_message(changes, message):
    with pytest.raises(ValueError, match=message):
        SecantBrief.model_validate(_brief_with(**changes))


def test_nan_is_rejected():
    with pytest.raises(ValueError, match="finite"):
        SecantBrief.model_validate(_brief_with(x0=float("nan")))


def test_load_brief_reads_valid_file(tmp_path):
    assert load_brief(_write(tmp_path, VALID_BRIEF)).x0 == 1.0


def test_load_brief_reports_missing_file(tmp_path):
    with pytest.raises(BriefError, match="not found"):
        load_brief(tmp_path / "nope.json")


def test_load_brief_reports_json_syntax_error_with_location(tmp_path):
    with pytest.raises(BriefError, match="not valid JSON .*line 1"):
        load_brief(_write(tmp_path, '{"topic": '))


def test_load_brief_lists_every_invalid_field(tmp_path):
    path = _write(tmp_path, _brief_with(function="sin(x)", h_start=-1))

    with pytest.raises(BriefError) as error:
        load_brief(path)

    text = str(error.value)
    assert "function" in text and "Unsupported function" in text
    assert "h_start" in text


def test_load_brief_rejects_non_object_json(tmp_path):
    with pytest.raises(BriefError, match="JSON object"):
        load_brief(_write(tmp_path, "[1, 2]"))


@pytest.mark.parametrize(
    "data, message",
    [
        ({"template": "pythagoras", "topic": "t", "a": 2, "b": 3}, "not form a Pythagorean triple"),
        ({"template": "pythagoras", "topic": "t", "a": 3.5, "b": 4}, "valid integer"),
        ({"template": "odd_sum", "topic": "t", "n": 20}, "less than or equal to 8"),
        ({"template": "spirograph", "topic": "t"}, "does not match any of the expected tags"),
    ],
)
def test_other_visual_briefs_are_validated(tmp_path, data, message):
    with pytest.raises(BriefError, match=message):
        load_brief(_write(tmp_path, data))


def test_brief_without_template_is_still_a_secant_brief(tmp_path):
    assert load_brief(_write(tmp_path, VALID_BRIEF)).template == "secant_tangent"
