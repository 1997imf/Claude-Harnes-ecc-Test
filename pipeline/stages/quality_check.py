"""Quality-check stage: video + storyboard + render facts -> qa_report.json.

Video checks use PyAV (bundled with Manim), so no ffmpeg/ffprobe executable
is needed. A check that cannot run is reported as "unavailable", which also
makes the report fail: nothing passes silently.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from pydantic import ValidationError

from pipeline.lesson import check_required
from pipeline.paths import ProjectPaths
from pipeline.runner import StageError
from pipeline.schemas import STORYBOARD_ADAPTER, CheckResult, LessonPlan, QAReport, RenderFacts
from pipeline.stages._io import read_model, write_model
from pipeline.visuals import VISUALS

MIN_DURATION_SECONDS = 5.0
MAX_DURATION_SECONDS = 60.0
DURATION_TOLERANCE_SECONDS = 1.0
SAMPLE_FRACTIONS = (0.25, 0.5, 0.95)
BLANK_PIXEL_THRESHOLD = 16  # 0-255; darker pixels count as background
MIN_CONTENT_FRACTION = 0.002  # at least 0.2% of pixels must be visible content
DRAWN_TOLERANCE = 1e-3  # relative; drawn geometry goes through screen coordinates


@dataclass(frozen=True)
class VideoInfo:
    width: int
    height: int
    fps: float
    frame_count: int
    duration: float
    sample_frames: tuple[np.ndarray, ...]


def check_video_file(video: Path) -> CheckResult:
    if not video.is_file():
        return CheckResult.of("video_file", False, f"{video.name} not found")
    size = video.stat().st_size
    return CheckResult.of("video_file", size > 0, f"{size} bytes" if size else "file is empty")


def _decode(video: Path) -> VideoInfo:
    import av  # imported here so a missing PyAV is reported, not a crash

    with av.open(str(video)) as container:
        stream = container.streams.video[0]
        frame_count = sum(1 for _ in container.decode(stream))
    if frame_count == 0:
        raise ValueError("video has no frames")
    wanted = {min(frame_count - 1, int(frame_count * f)) for f in SAMPLE_FRACTIONS}
    samples = []
    with av.open(str(video)) as container:
        stream = container.streams.video[0]
        fps = float(stream.average_rate)
        for index, frame in enumerate(container.decode(stream)):
            if index in wanted:
                samples.append(frame.to_ndarray(format="rgb24"))
        width, height = stream.codec_context.width, stream.codec_context.height
    return VideoInfo(width, height, fps, frame_count, frame_count / fps, tuple(samples))


def inspect_video(video: Path) -> tuple[CheckResult, VideoInfo | None]:
    try:
        import av.error
    except ImportError:
        return CheckResult(name="video_decodes", status="unavailable",
                           detail="PyAV is not installed; cannot decode video"), None
    try:
        info = _decode(video)
    except (av.error.FFmpegError, OSError, IndexError, ValueError, ZeroDivisionError) as error:
        return CheckResult.of("video_decodes", False, f"cannot decode: {error}"), None
    return CheckResult.of("video_decodes", True, f"{info.frame_count} frames at {info.fps:g} fps"), info


def check_resolution(info: VideoInfo, storyboard) -> CheckResult:
    size, expected = (info.width, info.height), storyboard.resolution
    return CheckResult.of("resolution", size == expected,
                  f"{size[0]}x{size[1]} (expected {expected[0]}x{expected[1]}, {storyboard.format})")


def check_duration(info: VideoInfo, storyboard) -> CheckResult:
    expected = storyboard.expected_duration
    in_limits = MIN_DURATION_SECONDS <= info.duration <= MAX_DURATION_SECONDS
    matches = abs(info.duration - expected) <= DURATION_TOLERANCE_SECONDS
    return CheckResult.of(
        "duration", in_limits and matches,
        f"{info.duration:.2f} s (storyboard {expected:.2f} s ± {DURATION_TOLERANCE_SECONDS:g}, "
        f"limits {MIN_DURATION_SECONDS:g}–{MAX_DURATION_SECONDS:g} s)",
    )


def check_frames(info: VideoInfo) -> CheckResult:
    fractions = [float((frame.max(axis=2) > BLANK_PIXEL_THRESHOLD).mean()) for frame in info.sample_frames]
    ok = bool(fractions) and all(f >= MIN_CONTENT_FRACTION for f in fractions)
    shown = ", ".join(f"{f:.1%}" for f in fractions)
    return CheckResult.of("frames_not_blank", ok, f"visible content in sampled frames: {shown}")


def _fact_mismatches(storyboard, facts: RenderFacts) -> list[str]:
    visual = VISUALS[storyboard.template]
    problems = []
    for name, expected in visual.expected_values(storyboard).items():
        measured = facts.values.get(name)
        if measured is None:
            problems.append(f"{name} was not measured by the template")
        elif abs(measured - expected) > DRAWN_TOLERANCE * max(1.0, abs(expected)):
            problems.append(f"{name} drawn as {measured:.4f}, expected {expected:g}")
    expected_labels = visual.expected_labels(storyboard)
    expected_labels |= {beat.caption for beat in storyboard.beats if beat.caption}
    missing = expected_labels - set(facts.labels)
    if missing:
        problems.append(f"missing labels: {sorted(missing)}")
    return problems


def check_rendered_values(storyboard, facts_path: Path) -> CheckResult:
    if not facts_path.is_file():
        return CheckResult.of("rendered_values", False, f"{facts_path.name} not found")
    try:
        facts = RenderFacts.model_validate_json(facts_path.read_text(encoding="utf-8"))
    except ValidationError as error:
        return CheckResult.of("rendered_values", False, f"{facts_path.name} is invalid: {error}")
    problems = _fact_mismatches(storyboard, facts)
    measured = ", ".join(sorted(VISUALS[storyboard.template].expected_values(storyboard)))
    detail = "; ".join(problems) or f"drawn values ({measured}) and all labels/captions match the storyboard"
    return CheckResult.of("rendered_values", not problems, detail)


def run_quality_checks(video: Path, storyboard, facts_path: Path,
                       lesson: LessonPlan | None = None) -> QAReport:
    checks = [check_video_file(video)]
    decode_check, info = inspect_video(video)
    checks.append(decode_check)
    if info is None:
        skipped = "skipped: video could not be decoded"
        checks += [CheckResult.of(name, False, skipped) for name in ("resolution", "duration", "frames_not_blank")]
    else:
        checks += [check_resolution(info, storyboard), check_duration(info, storyboard), check_frames(info)]
    checks += VISUALS[storyboard.template].check_math(storyboard)  # topic-specific math
    checks.append(check_rendered_values(storyboard, facts_path))
    if lesson is not None:  # must come last: it confirms the lesson's required checks ran and passed
        checks.append(check_required(lesson, checks))
    passed = all(check.status == "pass" for check in checks)
    return QAReport(passed=passed, video=video.name, checks=tuple(checks))


def run(paths: ProjectPaths) -> None:
    storyboard = read_model(paths.storyboard, STORYBOARD_ADAPTER)
    lesson = read_model(paths.lesson_plan, LessonPlan)
    report = run_quality_checks(paths.video, storyboard, paths.render_facts, lesson)
    report = report.model_copy(update={"video": paths.relative(paths.video)})
    write_model(paths.qa_report, report)
    if not report.passed:
        failed = [c.name for c in report.checks if c.status != "pass"]
        raise StageError(f"Quality checks failed: {', '.join(failed)}. See {paths.qa_report}")


def validate(paths: ProjectPaths) -> None:
    if not read_model(paths.qa_report, QAReport).passed:
        raise StageError("qa_report.json records failed checks")
