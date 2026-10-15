"""Sum of odd numbers visual: L-shaped layers of 1, 3, 5, ... unit cells build
an n × n square, showing 1 + 3 + ... + (2n − 1) = n².
"""

import re

from pipeline.schemas import (
    Beat, CheckResult, Definition, Equation, LessonPlan, OddSumBrief, OddSumClaim, OddSumParams,
    OddSumStoryboard,
)

TAGS = ("math", "algebra", "sequences", "odd numbers", "square numbers", "proof without words", "manim")
# Names returned by check_math (a test keeps them in sync).
CHECK_NAMES = frozenset({"odd_terms", "partial_sums_are_squares", "total", "sum_labels"})


def _running_sum(odds: tuple[int, ...]) -> str:
    terms = " + ".join(str(n) for n in odds)
    return terms if len(odds) == 1 else f"{terms} = {sum(odds)}"


def _beats(n: int) -> tuple[Beat, ...]:
    layers = []
    for k in range(1, n + 1):
        caption = "Start with 1 square" if k == 1 else f"Add {2 * k - 1} squares: now {k} × {k} = {k * k}"
        narration = ("Start with a single square." if k == 1 else
                     f"Wrap {2 * k - 1} more squares around it to make a {k} by {k} square of {k * k}.")
        layers.append(Beat(name=f"layer_{k}", description=f"Add the L-shaped layer of {2 * k - 1} cells",
                           run_time=1.5, caption=caption, narration=narration))
    beats = (
        Beat(name="title", description="Show the topic", run_time=1.0),
        *layers,
        Beat(name="result", description="State the pattern", run_time=2.0,
             caption=f"The first {n} odd numbers make {n}²",
             narration=f"Adding the first {n} odd numbers always gives a perfect square: {n} squared."),
        Beat(name="hold", description="Hold the final frame", run_time=2.0,
             caption=f"1 + 3 + … + {2 * n - 1} = {n}² = {n * n}"),
    )
    return beats


def build_lesson(brief: OddSumBrief) -> LessonPlan:
    """Deterministic lesson plan for a classic odd-sum brief."""
    n = brief.n
    odds = [2 * k - 1 for k in range(1, n + 1)]
    return LessonPlan(
        topic=brief.topic,
        learning_objective=brief.objective or (
            f"See why 1 + 3 + 5 + … + {2 * n - 1} = {n}² by wrapping L-shaped layers around a square."
        ),
        audience="middle_school",
        definitions=(
            Definition(term="odd number", meaning="a whole number of the form 2k − 1: 1, 3, 5, 7, …"),
            Definition(term="square number", meaning="n × n, the number of cells in an n by n square"),
        ),
        equations=(
            Equation(display=_running_sum(tuple(odds)) + f" = {n}²",
                     arithmetic=" + ".join(map(str, odds)) + f" == {n}**2"),
        ),
        results=(OddSumClaim(kind="odd_sum", n=n, total=n * n),),
        steps=tuple(beat.narration for beat in _beats(n) if beat.narration),
        examples=tuple(f"{_running_sum(tuple(odds[:k]))}" + ("" if k == 1 else f" = {k}²")
                       for k in range(2, n + 1)),
        conclusion=f"The first {n} odd numbers add up to {n}² = {n * n}.",
        visualization=OddSumParams(template="odd_sum", n=n),
        required_checks=tuple(sorted(CHECK_NAMES)) + ("rendered_values",),
    )


def build_storyboard(lesson: LessonPlan, video_format: str) -> OddSumStoryboard:
    n = lesson.visualization.n
    odds = tuple(2 * k - 1 for k in range(1, n + 1))
    partial = tuple(k * k for k in range(1, n + 1))
    return OddSumStoryboard(
        template="odd_sum",
        format=video_format,
        topic=lesson.topic,
        learning_objective=lesson.learning_objective,
        result=f"1 + 3 + … + {2 * n - 1} = {n}² = {n * n}",
        tags=TAGS,
        n=n,
        odd_numbers=odds,
        partial_sums=partial,
        sum_labels=tuple(_running_sum(odds[:k]) for k in range(1, n + 1)),
        beats=_beats(n),
    )


def check_math(storyboard: OddSumStoryboard) -> list[CheckResult]:
    n, odds, partial = storyboard.n, storyboard.odd_numbers, storyboard.partial_sums
    label_errors = []
    for k, label in enumerate(storyboard.sum_labels, start=1):
        numbers = [int(x) for x in re.findall(r"\d+", label)]
        terms, total = (numbers, numbers[0]) if k == 1 else (numbers[:-1], numbers[-1])
        if terms != list(odds[:k]) or sum(terms) != total or total != k * k:
            label_errors.append(label)
    return [
        CheckResult.of("odd_terms", odds == tuple(2 * k - 1 for k in range(1, n + 1)),
                       f"terms {list(odds)} are the first {n} odd numbers"),
        CheckResult.of("partial_sums_are_squares",
                       all(sum(odds[:k]) == partial[k - 1] == k * k for k in range(1, n + 1)),
                       f"running totals {list(partial)} equal 1², 2², …, {n}²"),
        CheckResult.of("total", sum(odds) == n * n, f"sum = {sum(odds)}, {n}² = {n * n}"),
        CheckResult.of("sum_labels", not label_errors and len(storyboard.sum_labels) == n,
                       "every on-screen running sum is correct" if not label_errors
                       else f"wrong labels: {label_errors}"),
    ]


def expected_values(storyboard: OddSumStoryboard) -> dict[str, float]:
    n = storyboard.n
    values: dict[str, float] = {f"layer_{k}_cells": 2 * k - 1 for k in range(1, n + 1)}
    values |= {"total_cells": n * n, "square_width_cells": n, "square_height_cells": n}
    return values


def expected_labels(storyboard: OddSumStoryboard) -> set[str]:
    return set(storyboard.sum_labels)
