"""Data shapes passed between stages, validated with pydantic.

Every JSON file a stage reads is validated here first, so malformed input
stops the pipeline early with a readable message.
"""

import json
import math
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from pipeline.functions import get_function

H_END = 0.01  # smallest h shown; h = 0 is undefined because the slope divides by h
X0_LIMIT = 3.0
H_START_MAX = 3.0
TOPIC_MAX_LENGTH = 120


class BriefError(ValueError):
    """The brief file is missing, unreadable, or invalid."""


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Brief(_Frozen):
    topic: str = Field(max_length=TOPIC_MAX_LENGTH)
    function: str
    x0: float = Field(ge=-X0_LIMIT, le=X0_LIMIT, allow_inf_nan=False)
    h_start: float = Field(gt=H_END, le=H_START_MAX, allow_inf_nan=False)

    @field_validator("x0", "h_start", mode="before")
    @classmethod
    def _require_json_number(cls, value: object) -> object:
        # JSON true/"1" would otherwise be silently converted to 1.0.
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError("must be a number")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("must be a finite number")
        return value

    @field_validator("topic")
    @classmethod
    def _strip_topic(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("topic must not be empty")
        return value.strip()

    @field_validator("function")
    @classmethod
    def _supported_function(cls, value: str) -> str:
        return get_function(value).expression


class AxesSpec(_Frozen):
    x_min: float
    x_max: float
    x_step: float
    y_min: float
    y_max: float
    y_step: float


class Beat(_Frozen):
    name: str
    description: str
    run_time: float = Field(gt=0)


class Storyboard(_Frozen):
    schema_version: Literal[1] = 1
    template: Literal["secant_tangent"]
    topic: str
    function: str
    x0: float
    y0: float
    h_start: float
    h_end: float
    derivative: float
    tangent_intercept: float
    function_label: str
    point_label: str
    secant_slope_label: str
    tangent_label: str
    axes: AxesSpec
    beats: tuple[Beat, ...]

    @property
    def expected_duration(self) -> float:
        return sum(beat.run_time for beat in self.beats)

    def run_time(self, beat_name: str) -> float:
        return next(beat.run_time for beat in self.beats if beat.name == beat_name)


class SceneParams(_Frozen):
    """What the generate stage hands to the Manim template."""

    template_file: str
    template_sha256: str
    scene_class: str
    storyboard: Storyboard


class RenderFacts(_Frozen):
    """Values measured from the objects the template actually drew."""

    point: tuple[float, float]
    tangent_slope: float
    tangent_intercept: float
    final_h: float
    final_secant_slope: float
    labels: list[str]


class CheckResult(_Frozen):
    name: str
    status: Literal["pass", "fail", "unavailable"]
    detail: str


class QAReport(_Frozen):
    passed: bool
    video: str
    checks: tuple[CheckResult, ...]


def _format_validation_error(error: ValidationError) -> str:
    lines = []
    for issue in error.errors():
        field = ".".join(str(part) for part in issue["loc"]) or "(brief)"
        message = issue["msg"].removeprefix("Value error, ")
        lines.append(f"  - {field}: {message}")
    return "\n".join(lines)


def load_brief(path: Path) -> Brief:
    """Read and validate brief.json, raising BriefError with a readable message."""
    if not path.is_file():
        raise BriefError(f"Brief file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise BriefError(
            f"{path} is not valid JSON (line {error.lineno}, column {error.colno}): {error.msg}"
        ) from error
    if not isinstance(data, dict):
        raise BriefError(f"{path} must contain a JSON object like {{\"topic\": ...}}")
    try:
        return Brief.model_validate(data)
    except ValidationError as error:
        raise BriefError(f"{path} is invalid:\n{_format_validation_error(error)}") from error
