"""Package stage: write metadata.json for publishing and preview.html for viewing.

Nothing is uploaded; the metadata is ready for a future YouTube/Instagram step.
"""

from html import escape

from pipeline.functions import format_number
from pipeline.paths import ProjectPaths
from pipeline.runner import StageError
from pipeline.schemas import PublishMetadata, QAReport, Storyboard
from pipeline.stages._io import read_model, write_model
from pipeline.stages.quality_check import inspect_video

BASE_TAGS = ("math", "calculus", "derivative", "limits", "secant line", "tangent line", "manim")
BASE_HASHTAGS = ("#math", "#calculus", "#derivative", "#learnmath")
SHORTS_HASHTAG = "#shorts"


def build_metadata(storyboard: Storyboard, report: QAReport, width: int, height: int,
                   duration: float) -> PublishMetadata:
    hashtags = BASE_HASHTAGS + ((SHORTS_HASHTAG,) if storyboard.format == "portrait" else ())
    steps = "\n".join(f"• {beat.narration}" for beat in storyboard.beats if beat.narration)
    answer = (f"Result: f′({format_number(storyboard.x0)}) = {format_number(storyboard.derivative)} "
              f"for {storyboard.function_label}.")
    description = (
        f"{storyboard.learning_objective}\n\n{steps}\n\n{answer}\n"
        "Animated with Manim; the math was checked automatically.\n\n" + " ".join(hashtags)
    )
    caption = f"{storyboard.topic}\n\n{storyboard.learning_objective}\n{answer}\n\n" + " ".join(hashtags)
    return PublishMetadata(
        title=storyboard.topic, description=description, tags=BASE_TAGS, hashtags=hashtags,
        instagram_caption=caption, video=report.video, format=storyboard.format,
        width=width, height=height, duration_seconds=round(duration, 2), qa_passed=report.passed,
    )

_STYLE = """
:root { --bg: #ffffff; --fg: #1d1d1f; --muted: #6e6e73; --line: #d2d2d7;
        --pass: #1a7f37; --fail: #c62828; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #161618; --fg: #f5f5f7; --muted: #a1a1a6; --line: #3a3a3c;
          --pass: #4ac26b; --fail: #ff6b6b; }
}
body { margin: 0 auto; max-width: 900px; padding: 24px 16px; background: var(--bg);
       color: var(--fg); font: 16px/1.5 -apple-system, system-ui, sans-serif; }
video { width: 100%; border-radius: 8px; background: #000; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }
.muted { color: var(--muted); }
.pass { color: var(--pass); font-weight: 600; }
.fail, .unavailable { color: var(--fail); font-weight: 600; }
"""


def _check_rows(report: QAReport) -> str:
    return "\n".join(
        f'<tr><td>{escape(c.name)}</td><td class="{escape(c.status)}">{escape(c.status)}</td>'
        f"<td>{escape(c.detail)}</td></tr>"
        for c in report.checks
    )


def _metadata_section(metadata: PublishMetadata | None) -> str:
    if metadata is None:
        return ""
    return (
        "<h2>Publishing metadata</h2>\n"
        f"<p><strong>{escape(metadata.title)}</strong> · {metadata.width}×{metadata.height} · "
        f"{metadata.duration_seconds:g} s</p>\n"
        f'<pre style="white-space: pre-wrap">{escape(metadata.description)}</pre>\n'
    )


def build_preview_html(storyboard: Storyboard, report: QAReport, video_href: str,
                       metadata: PublishMetadata | None = None) -> str:
    verdict = "All checks passed" if report.passed else "Some checks failed"
    verdict_class = "pass" if report.passed else "fail"
    topic = escape(storyboard.topic)
    facts = (
        f"{escape(storyboard.function_label)} · x₀ = {storyboard.x0:g} · "
        f"h: {storyboard.h_start:g} → {storyboard.h_end:g} · "
        f"f′(x₀) = {storyboard.derivative:g} · {escape(storyboard.tangent_label)}"
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Preview: {topic}</title>
<style>{_STYLE}</style>
</head>
<body>
<h1>{topic}</h1>
<p class="muted">{facts}</p>
<video controls src="{escape(video_href)}" style="max-height: 80vh"></video>
{_metadata_section(metadata)}
<h2>Quality checks: <span class="{verdict_class}">{verdict}</span></h2>
<table>
<tr><th>Check</th><th>Status</th><th>Detail</th></tr>
{_check_rows(report)}
</table>
<p class="muted">Generated locally by the pipeline. Nothing has been uploaded.</p>
</body>
</html>
"""


def run(paths: ProjectPaths) -> None:
    storyboard = read_model(paths.storyboard, Storyboard)
    report = read_model(paths.qa_report, QAReport)
    decoded, info = inspect_video(paths.video)
    if info is None:
        raise StageError(f"Cannot read the video for metadata: {decoded.detail}")
    metadata = build_metadata(storyboard, report, info.width, info.height, info.duration)
    write_model(paths.metadata, metadata)
    video_href = paths.video.relative_to(paths.preview.parent).as_posix()
    html = build_preview_html(storyboard, report, video_href, metadata)
    paths.preview.write_text(html, encoding="utf-8")
