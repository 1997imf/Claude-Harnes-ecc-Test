"""Package stage: write preview.html showing the video, the math, and the QA results."""

from html import escape

from pipeline.paths import ProjectPaths
from pipeline.schemas import QAReport, Storyboard
from pipeline.stages._io import read_model

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


def build_preview_html(storyboard: Storyboard, report: QAReport, video_href: str) -> str:
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
<video controls src="{escape(video_href)}"></video>
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
    video_href = paths.video.relative_to(paths.preview.parent).as_posix()
    paths.preview.write_text(build_preview_html(storyboard, report, video_href), encoding="utf-8")
