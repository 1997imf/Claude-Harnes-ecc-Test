"""Pythagorean theorem visual: squares on the sides of a right triangle, drawn as
unit-cell grids, so a² + b² = c² can be checked by counting.

Only Pythagorean triples are accepted (whole-number hypotenuse), so every
area shown is an exact integer that the template can draw cell by cell.
"""

import math
import re

from pipeline.schemas import (
    Beat, CheckResult, Definition, Equation, LessonPlan, PythagorasBrief, PythagorasParams,
    PythagoreanClaim, PythagorasStoryboard,
)

TAGS = ("math", "geometry", "pythagorean theorem", "right triangle", "area", "manim")
RIGHT_ANGLE_DEGREES = 90.0
# Names returned by check_math (a test keeps them in sync).
CHECK_NAMES = frozenset({"pythagorean_triple", "triangle_inequality", "equation_label"})


def _beats(a: int, b: int, c: int) -> tuple[Beat, ...]:
    sq_a, sq_b, sq_c = a * a, b * b, c * c
    return (
        Beat(name="title", description="Show the topic", run_time=1.0),
        Beat(name="triangle", description="Draw the right triangle and its side lengths", run_time=2.0,
             caption=f"A right triangle with legs {a} and {b}",
             narration=f"Here is a right triangle with legs {a} and {b} and hypotenuse {c}."),
        Beat(name="square_a", description="Square on leg a, as a grid of unit cells", run_time=2.0,
             caption=f"Leg {a}: square of area {a}² = {sq_a}",
             narration=f"The square on the leg of length {a} holds {sq_a} unit squares."),
        Beat(name="square_b", description="Square on leg b, as a grid of unit cells", run_time=2.0,
             caption=f"Leg {b}: square of area {b}² = {sq_b}",
             narration=f"The square on the leg of length {b} holds {sq_b} unit squares."),
        Beat(name="square_c", description="Square on the hypotenuse, as a grid of unit cells", run_time=2.5,
             caption=f"Hypotenuse {c}: area {c}² = {sq_c}",
             narration=f"The square on the hypotenuse, of length {c}, holds {sq_c} unit squares."),
        Beat(name="equation", description="Write the area equation", run_time=2.0,
             caption="The two smaller areas add up to the largest",
             narration=f"Add the two smaller areas: {sq_a} plus {sq_b} is {sq_c}."),
        Beat(name="hold", description="Hold the final frame", run_time=2.0,
             caption=f"So {a}² + {b}² = {c}²",
             narration=f"So {a} squared plus {b} squared equals {c} squared."),
    )


def build_lesson(brief: PythagorasBrief) -> LessonPlan:
    """Deterministic lesson plan for a classic Pythagoras brief."""
    a, b = brief.a, brief.b
    c = math.isqrt(a * a + b * b)
    return LessonPlan(
        topic=brief.topic,
        learning_objective=brief.objective or (
            f"See that {a}² + {b}² = {c}² by counting the unit squares built on each side "
            "of a right triangle."
        ),
        audience="middle_school",
        definitions=(
            Definition(term="right triangle", meaning="a triangle with one 90° angle"),
            Definition(term="legs", meaning="the two sides that meet at the right angle"),
            Definition(term="hypotenuse", meaning="the longest side, opposite the right angle"),
        ),
        equations=(
            Equation(display=f"{a}² + {b}² = {c}²", arithmetic=f"{a}**2 + {b}**2 == {c}**2"),
            Equation(display=f"{a * a} + {b * b} = {c * c}", arithmetic=f"{a * a} + {b * b} == {c * c}"),
        ),
        results=(PythagoreanClaim(kind="pythagorean", a=a, b=b, c=c),),
        steps=tuple(beat.narration for beat in _beats(a, b, c) if beat.narration),
        examples=(f"A {a}-{b}-{c} triangle: {a * a} + {b * b} = {c * c} unit squares.",),
        conclusion=f"For a right triangle the two leg squares fill the hypotenuse square: {a}² + {b}² = {c}².",
        visualization=PythagorasParams(template="pythagoras", a=a, b=b),
        required_checks=tuple(sorted(CHECK_NAMES)) + ("rendered_values",),
    )


def build_storyboard(lesson: LessonPlan, video_format: str) -> PythagorasStoryboard:
    a, b = lesson.visualization.a, lesson.visualization.b
    c = math.isqrt(a * a + b * b)
    sq_a, sq_b, sq_c = a * a, b * b, c * c
    return PythagorasStoryboard(
        template="pythagoras",
        format=video_format,
        topic=lesson.topic,
        learning_objective=lesson.learning_objective,
        result=f"{a}² + {b}² = {c}² ({sq_a} + {sq_b} = {sq_c})",
        tags=TAGS,
        a=a, b=b, c=c,
        equation_label=f"{sq_a} + {sq_b} = {sq_c}",
        beats=_beats(a, b, c),
    )


def check_math(storyboard: PythagorasStoryboard) -> list[CheckResult]:
    a, b, c = storyboard.a, storyboard.b, storyboard.c
    shown = [int(n) for n in re.findall(r"\d+", storyboard.equation_label)]
    return [
        CheckResult.of("pythagorean_triple", a * a + b * b == c * c,
                       f"{a}² + {b}² = {a * a + b * b}, {c}² = {c * c}"),
        CheckResult.of("triangle_inequality", a + b > c and a + c > b and b + c > a,
                       f"sides {a}, {b}, {c} form a triangle"),
        CheckResult.of("equation_label",
                       len(shown) == 3 and shown == [a * a, b * b, c * c] and shown[0] + shown[1] == shown[2],
                       f"on-screen {storyboard.equation_label!r} parsed as {shown}"),
    ]


def expected_values(storyboard: PythagorasStoryboard) -> dict[str, float]:
    a, b, c = storyboard.a, storyboard.b, storyboard.c
    return {
        "leg_a": a, "leg_b": b, "hypotenuse": c,
        "right_angle_deg": RIGHT_ANGLE_DEGREES,
        "area_a": a * a, "area_b": b * b, "area_c": c * c,
        "cells_a": a * a, "cells_b": b * b, "cells_c": c * c,
    }


def expected_labels(storyboard: PythagorasStoryboard) -> set[str]:
    return {storyboard.equation_label,
            f"a = {storyboard.a}", f"b = {storyboard.b}", f"c = {storyboard.c}"}
