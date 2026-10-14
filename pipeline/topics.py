"""Automatic topic selection from a catalog of verified topics.

Each topic names a reviewed visual (`template`) and its example values. Numbers
shown in the video are not typed here; the visual derives them and checks them
before rendering. Catalog order is the teaching priority.

Selection, per video format:
1. an explicitly requested topic (for debugging/reproducibility), else
2. a never-produced topic, preferring a different visual type from the most
   recently produced video (variety), else
3. the least recently produced topic.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pipeline.manifest import ManifestError, load_manifest
from pipeline.paths import BRIEF_FILENAME


@dataclass(frozen=True)
class Topic:
    id: str
    title: str
    template: str
    params: dict[str, Any] = field(default_factory=dict)


CATALOG: tuple[Topic, ...] = (
    Topic("slope-x2-at-1", "Derivative as the limit of secants", "secant_tangent",
          {"function": "x**2", "x0": 1.0, "h_start": 1.5}),
    Topic("pythagoras-3-4-5", "Pythagoras by counting squares", "pythagoras", {"a": 3, "b": 4}),
    Topic("odd-sum-4", "Odd numbers build squares", "odd_sum", {"n": 4}),
    Topic("slope-x3-at-1", "How steep is x³ at x = 1?", "secant_tangent",
          {"function": "x**3", "x0": 1.0, "h_start": 1.0}),
    Topic("pythagoras-5-12-13", "A 5-12-13 right triangle", "pythagoras", {"a": 5, "b": 12}),
    Topic("odd-sum-6", "Why 1 + 3 + … + 11 = 36", "odd_sum", {"n": 6}),
    Topic("slope-x2-at-minus-1", "A tangent that slopes downward", "secant_tangent",
          {"function": "x**2", "x0": -1.0, "h_start": 1.5}),
    Topic("slope-x2-at-2", "How steep is x² at x = 2?", "secant_tangent",
          {"function": "x**2", "x0": 2.0, "h_start": 1.0}),
    Topic("slope-x3-at-minus-1", "x³ at x = −1: secants to tangent", "secant_tangent",
          {"function": "x**3", "x0": -1.0, "h_start": 1.0}),
)


def project_slug(topic: Topic, video_format: str) -> str:
    return f"{topic.id}-{video_format}"


def _last_success(project_dir: Path) -> str | None:
    """Time the package stage last completed, or None if never produced."""
    try:
        manifest = load_manifest(project_dir / "manifest.json")
    except ManifestError:
        return None
    if manifest is None:
        return None
    record = manifest.stages.get("package")
    return record.finished_at if record and record.status == "completed" else None


def select_topic(projects_dir: Path, video_format: str, topic_id: str | None = None) -> Topic:
    if topic_id is not None:
        for topic in CATALOG:
            if topic.id == topic_id:
                return topic
        raise ValueError(f"Unknown topic {topic_id!r}. Available: {', '.join(t.id for t in CATALOG)}")
    produced = {t.id: _last_success(projects_dir / project_slug(t, video_format)) for t in CATALOG}
    done = [t for t in CATALOG if produced[t.id] is not None]
    fresh = [t for t in CATALOG if produced[t.id] is None]
    if fresh:
        last_template = max(done, key=lambda t: produced[t.id]).template if done else None
        different = [t for t in fresh if t.template != last_template]
        return (different or fresh)[0]
    return min(CATALOG, key=lambda t: produced[t.id])


def write_topic_brief(topic: Topic, video_format: str, projects_dir: Path) -> Path:
    """Write projects/<slug>/brief.json for the topic (idempotent)."""
    brief_path = projects_dir / project_slug(topic, video_format) / BRIEF_FILENAME
    brief = {"template": topic.template, "topic": topic.title, "format": video_format, **topic.params}
    brief_path.parent.mkdir(parents=True, exist_ok=True)
    brief_path.write_text(json.dumps(brief, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return brief_path
