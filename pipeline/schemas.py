"""Data shapes passed between stages, validated with pydantic.

Every JSON file a stage reads is validated here first, so malformed input
stops the pipeline early with a readable message.

Each visualization type ("template") has its own brief and storyboard shape;
`Brief` and `Storyboard` are unions that pick the right shape from the
`template` field. A brief without a `template` field is a secant_tangent brief
(the original format), so older projects keep working.
"""

import json
import math
from pathlib import Path
from typing import Annotated, Literal, Union, get_args

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, field_validator

from pipeline.arithmetic import parse_equation
from pipeline.functions import get_function

H_END = 0.01  # smallest h shown; h = 0 is undefined because the slope divides by h
X0_LIMIT = 3.0
H_START_MAX = 3.0
TOPIC_MAX_LENGTH = 120
OBJECTIVE_MAX_LENGTH = 200
LEG_MAX = 12  # keeps the unit-cell grids readable (at most 13 x 13 cells on the hypotenuse)
ODD_SUM_MAX_TERMS = 8
DEFAULT_TEMPLATE = "secant_tangent"

VideoFormat = Literal["landscape", "portrait"]
# Pixel size per format at the MVP's low render quality (Manim -ql, 15 fps).
RESOLUTIONS: dict[str, tuple[int, int]] = {"landscape": (854, 480), "portrait": (480, 854)}


class BriefError(ValueError):
    """The brief file is missing, unreadable, or invalid."""


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# --- briefs (input) -------------------------------------------------------------

class _BriefBase(_Frozen):
    topic: str = Field(max_length=TOPIC_MAX_LENGTH)
    format: VideoFormat = "landscape"
    objective: str | None = Field(default=None, max_length=OBJECTIVE_MAX_LENGTH)

    @field_validator("topic")
    @classmethod
    def _strip_topic(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("topic must not be empty")
        return value.strip()


def _require_json_number(value: object) -> object:
    # JSON true/"1" would otherwise be silently converted to a number.
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("must be a number")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("must be a finite number")
    return value


# --- visualization parameters (shared by briefs and lesson plans) ---------------------

class SecantParams(_Frozen):
    template: Literal["secant_tangent"] = "secant_tangent"
    function: str
    x0: float = Field(ge=-X0_LIMIT, le=X0_LIMIT, allow_inf_nan=False)
    h_start: float = Field(gt=H_END, le=H_START_MAX, allow_inf_nan=False)

    @field_validator("x0", "h_start", mode="before")
    @classmethod
    def _numbers(cls, value: object) -> object:
        return _require_json_number(value)

    @field_validator("function")
    @classmethod
    def _supported_function(cls, value: str) -> str:
        return get_function(value).expression


class PythagorasParams(_Frozen):
    template: Literal["pythagoras"]
    a: int = Field(ge=1, le=LEG_MAX, strict=True)
    b: int = Field(ge=1, le=LEG_MAX, strict=True)

    @field_validator("b")
    @classmethod
    def _integer_hypotenuse(cls, b: int, info) -> int:
        a = info.data.get("a")
        if a is not None and math.isqrt(a * a + b * b) ** 2 != a * a + b * b:
            raise ValueError(f"legs {a} and {b} do not form a Pythagorean triple "
                             "(the hypotenuse must be a whole number to count unit squares)")
        return b


class OddSumParams(_Frozen):
    template: Literal["odd_sum"]
    n: int = Field(ge=2, le=ODD_SUM_MAX_TERMS, strict=True)


PARAM_TYPES = (SecantParams, PythagorasParams, OddSumParams)
# Template names come from each class's `template` Literal, so they are defined once.
TEMPLATE_NAMES = frozenset(get_args(cls.model_fields["template"].annotation)[0] for cls in PARAM_TYPES)
Visualization = Annotated[Union[PARAM_TYPES], Field(discriminator="template")]


# A classic brief = visualization parameters + presentation fields (topic, format, objective).
class SecantBrief(_BriefBase, SecantParams):
    pass


class PythagorasBrief(_BriefBase, PythagorasParams):
    pass


class OddSumBrief(_BriefBase, OddSumParams):
    pass


BRIEF_TYPES = (SecantBrief, PythagorasBrief, OddSumBrief)
Brief = Annotated[Union[BRIEF_TYPES], Field(discriminator="template")]
BRIEF_ADAPTER = TypeAdapter(Brief)


# --- lesson plans (what to teach; rendering-independent) ----------------------------------

Audience = Literal["middle_school", "high_school", "intro_university"]
ARITHMETIC_MAX_LENGTH = 200


class Definition(_Frozen):
    term: str = Field(min_length=1)
    meaning: str = Field(min_length=1)


class Equation(_Frozen):
    """An equation as shown to the viewer, optionally with a checkable arithmetic form."""

    display: str = Field(min_length=1)
    # e.g. "3**2 + 4**2 == 5**2": numbers, + - * / ** and parentheses, exactly one ==.
    arithmetic: str | None = Field(default=None, max_length=ARITHMETIC_MAX_LENGTH)

    @field_validator("arithmetic")
    @classmethod
    def _safe_arithmetic(cls, value: str | None) -> str | None:
        if value is not None:
            parse_equation(value)  # validates the syntax without evaluating it
        return value


class DerivativeClaim(_Frozen):
    kind: Literal["derivative"]
    function: str
    at: float
    value: float

    @field_validator("function")
    @classmethod
    def _supported_function(cls, value: str) -> str:
        return get_function(value).expression


class PythagoreanClaim(_Frozen):
    kind: Literal["pythagorean"]
    a: int = Field(strict=True)
    b: int = Field(strict=True)
    c: int = Field(strict=True)


class OddSumClaim(_Frozen):
    kind: Literal["odd_sum"]
    n: int = Field(strict=True)
    total: int = Field(strict=True)


Claim = Annotated[DerivativeClaim | PythagoreanClaim | OddSumClaim, Field(discriminator="kind")]


class LessonPlan(_Frozen):
    """Structured math content. Rendering details (timing, layout, format) live elsewhere."""

    schema_version: Literal[1] = 1
    topic: str = Field(min_length=1, max_length=TOPIC_MAX_LENGTH)
    learning_objective: str = Field(min_length=1)
    audience: Audience
    definitions: tuple[Definition, ...] = ()
    equations: tuple[Equation, ...] = ()
    results: tuple[Claim, ...] = Field(min_length=1)  # verified before rendering
    steps: tuple[str, ...] = Field(min_length=2)
    examples: tuple[str, ...] = ()
    conclusion: str = Field(min_length=1)
    visualization: Visualization
    required_checks: tuple[str, ...] = Field(min_length=1)


class LessonBrief(_Frozen):
    """A brief that supplies a ready-made lesson plan (e.g. from a future AI planner)."""

    format: VideoFormat = "landscape"
    lesson: LessonPlan


# --- storyboards (plan stage output) -------------------------------------------------

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
    caption: str = ""  # on-screen explanation shown during this beat ("" keeps the previous one)
    narration: str = ""  # script line for future voice-over; not rendered yet


class _StoryboardBase(_Frozen):
    schema_version: Literal[3] = 3
    format: VideoFormat
    topic: str
    learning_objective: str
    result: str  # the main mathematical result, e.g. "f′(1) = 2 for f(x) = x²"
    tags: tuple[str, ...]
    beats: tuple[Beat, ...]

    @property
    def expected_duration(self) -> float:
        return sum(beat.run_time for beat in self.beats)

    def run_time(self, beat_name: str) -> float:
        return self.beat(beat_name).run_time

    def beat(self, beat_name: str) -> Beat:
        return next(beat for beat in self.beats if beat.name == beat_name)

    @property
    def resolution(self) -> tuple[int, int]:
        return RESOLUTIONS[self.format]


class SecantStoryboard(_StoryboardBase):
    template: Literal["secant_tangent"]
    function: str
    x0: float
    y0: float
    h_start: float
    h_end: float
    derivative: float
    tangent_intercept: float
    secant_coefficients: tuple[float, float, float]  # secant slope = a + b*h + c*h^2
    function_label: str
    point_label: str
    secant_slope_label: str
    tangent_label: str
    axes: AxesSpec


class PythagorasStoryboard(_StoryboardBase):
    template: Literal["pythagoras"]
    a: int
    b: int
    c: int
    equation_label: str  # e.g. "9 + 16 = 25"


class OddSumStoryboard(_StoryboardBase):
    template: Literal["odd_sum"]
    n: int
    odd_numbers: tuple[int, ...]
    partial_sums: tuple[int, ...]
    sum_labels: tuple[str, ...]  # running sum shown after each layer, e.g. "1 + 3 = 4"


Storyboard = Annotated[
    SecantStoryboard | PythagorasStoryboard | OddSumStoryboard, Field(discriminator="template")
]
STORYBOARD_ADAPTER = TypeAdapter(Storyboard)


class SceneParams(_Frozen):
    """What the render stage hands to the Manim template."""

    template_file: str
    template_sha256: str
    scene_class: str
    storyboard: Storyboard


class RenderFacts(_Frozen):
    """What the template actually drew: measured values and every text label shown."""

    values: dict[str, float]
    labels: list[str]


# --- QA and publishing ------------------------------------------------------------------

class CheckResult(_Frozen):
    name: str
    status: Literal["pass", "fail", "unavailable"]
    detail: str

    @classmethod
    def of(cls, name: str, ok: bool, detail: str) -> "CheckResult":
        return cls(name=name, status="pass" if ok else "fail", detail=detail)


class QAReport(_Frozen):
    passed: bool
    video: str
    checks: tuple[CheckResult, ...]


# Platform limits (YouTube title 100 chars, description 5000; Instagram caption 2200, 30 hashtags).
class PublishMetadata(_Frozen):
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(max_length=5000)
    tags: tuple[str, ...]
    hashtags: tuple[str, ...] = Field(max_length=30)
    instagram_caption: str = Field(max_length=2200)
    video: str
    format: VideoFormat
    width: int
    height: int
    duration_seconds: float
    qa_passed: bool


def _format_validation_error(error: ValidationError) -> str:
    lines = []
    for issue in error.errors():
        loc = [str(part) for part in issue["loc"]]
        if loc and loc[0] in TEMPLATE_NAMES:  # drop the union branch name for readability
            loc = loc[1:]
        message = issue["msg"].removeprefix("Value error, ")
        lines.append(f"  - {'.'.join(loc) or '(brief)'}: {message}")
    return "\n".join(lines)


def load_brief(path: Path) -> SecantBrief | PythagorasBrief | OddSumBrief | LessonBrief:
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
        if "lesson" in data:  # a ready-made lesson plan rather than a classic brief
            return LessonBrief.model_validate(data)
        return BRIEF_ADAPTER.validate_python({"template": DEFAULT_TEMPLATE, **data})
    except ValidationError as error:
        raise BriefError(f"{path} is invalid:\n{_format_validation_error(error)}") from error
