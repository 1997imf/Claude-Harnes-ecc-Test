"""Automatic topic selection from a small catalog of verified topics.

Every topic uses the secant-to-tangent template with a whitelisted function, so
the pipeline can check all of its math. Numbers in titles/captions are not
typed here; the plan stage derives them from the function and checks them.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from pipeline.manifest import ManifestError, load_manifest
from pipeline.paths import BRIEF_FILENAME


@dataclass(frozen=True)
class Topic:
    id: str
    title: str
    function: str
    x0: float
    h_start: float


CATALOG: tuple[Topic, ...] = (
    Topic("slope-x2-at-1", "Derivative as the limit of secants", "x**2", 1.0, 1.5),
    Topic("slope-x3-at-1", "How steep is x³ at x = 1?", "x**3", 1.0, 1.0),
    Topic("slope-x2-at-minus-1", "A tangent that slopes downward", "x**2", -1.0, 1.5),
    Topic("slope-x2-at-2", "How steep is x² at x = 2?", "x**2", 2.0, 1.0),
    Topic("slope-x3-at-minus-1", "x³ at x = −1: secants to tangent", "x**3", -1.0, 1.0),
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
    """Pick the requested topic, else the first never-produced one, else the least recent."""
    if topic_id is not None:
        for topic in CATALOG:
            if topic.id == topic_id:
                return topic
        raise ValueError(f"Unknown topic {topic_id!r}. Available: {', '.join(t.id for t in CATALOG)}")
    produced = {t.id: _last_success(projects_dir / project_slug(t, video_format)) for t in CATALOG}
    fresh = [t for t in CATALOG if produced[t.id] is None]
    if fresh:
        return fresh[0]
    return min(CATALOG, key=lambda t: produced[t.id])


def write_topic_brief(topic: Topic, video_format: str, projects_dir: Path) -> Path:
    """Write projects/<slug>/brief.json for the topic (idempotent)."""
    brief_path = projects_dir / project_slug(topic, video_format) / BRIEF_FILENAME
    brief = {
        "topic": topic.title,
        "function": topic.function,
        "x0": topic.x0,
        "h_start": topic.h_start,
        "format": video_format,
    }
    brief_path.parent.mkdir(parents=True, exist_ok=True)
    brief_path.write_text(json.dumps(brief, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return brief_path
