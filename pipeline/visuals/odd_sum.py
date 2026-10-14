"""Sum of odd numbers visual: L-shaped layers of 1, 3, 5, ... unit cells build
an n × n square, showing 1 + 3 + ... + (2n − 1) = n².
"""

import re

from pipeline.schemas import Beat, CheckResult, OddSumBrief, OddSumStoryboard

TAGS = ("math", "algebra", "sequences", "odd numbers", "square numbers", "proof without words", "manim")


def _running_sum(odds: tuple[int, ...]) -> str:
    terms = " + ".join(str(n) for n in odds)
    return terms if len(odds) == 1 else f"{terms} = {sum(odds)}"


def build_storyboard(brief: OddSumBrief) -> OddSumStoryboard:
    n = brief.n
    odds = tuple(2 * k - 1 for k in range(1, n + 1))
    partial = tuple(k * k for k in range(1, n + 1))
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
    return OddSumStoryboard(
        template="odd_sum",
        format=brief.format,
        topic=brief.topic,
        learning_objective=brief.objective or (
            f"See why 1 + 3 + 5 + … + {2 * n - 1} = {n}² by wrapping L-shaped layers around a square."
        ),
        result=f"1 + 3 + … + {2 * n - 1} = {n}² = {n * n}",
        tags=TAGS,
        n=n,
        odd_numbers=odds,
        partial_sums=partial,
        sum_labels=tuple(_running_sum(odds[:k]) for k in range(1, n + 1)),
        beats=beats,
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
