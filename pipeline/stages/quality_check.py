"""Quality-check stage: video + storyboard + render facts -> qa_report.json.

Video checks use PyAV (bundled with Manim), so no ffmpeg/ffprobe executable
is needed. A check that cannot run is reported as "unavailable", which also
makes the report fail: nothing passes silently.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from pydantic import ValidationError

from pipeline.functions import (
    format_line_equation,
    get_function,
    numeric_derivative,
    secant_slope,
    tangent_line,
)
from pipeline.paths import ProjectPaths
from pipeline.runner import StageError
from pipeline.schemas import CheckResult, QAReport, RenderFacts, Storyboard
from pipeline.stages._io import read_model, write_model

EXPECTED_SIZE = (854, 480)
MIN_DURATION_SECONDS = 5.0
MAX_DURATION_SECONDS = 60.0
DURATION_TOLERANCE_SECONDS = 1.0
SAMPLE_FRACTIONS = (0.25, 0.5, 0.95)
BLANK_PIXEL_THRESHOLD = 16  # 0-255; darker pixels count as background
MIN_CONTENT_FRACTION = 0.002  # at least 0.2% of pixels must be visible content
MATH_TOLERANCE = 1e-6
DRAWN_TOLERANCE = 1e-3  # drawn geometry goes through screen coordinates
SECANT_CONVERGENCE_TOLERANCE = 0.1


@dataclass(frozen=True)
class VideoInfo:
    width: int
    height: int
    fps: float
    frame_count: int
    duration: float
    sample_frames: tuple[np.ndarray, ...]


def _check(name: str, ok: bool, detail: str) -> CheckResult:
    return CheckResult(name=name, status="pass" if ok else "fail", detail=detail)


def check_video_file(video: Path) -> CheckResult:
    if not video.is_file():
        return _check("video_file", False, f"{video.name} not found")
    size = video.stat().st_size
    return _check("video_file", size > 0, f"{size} bytes" if size else "file is empty")


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
        return _check("video_decodes", False, f"cannot decode: {error}"), None
    return _check("video_decodes", True, f"{info.frame_count} frames at {info.fps:g} fps"), info


def check_resolution(info: VideoInfo) -> CheckResult:
    size = (info.width, info.height)
    return _check("resolution", size == EXPECTED_SIZE, f"{size[0]}x{size[1]} (expected 854x480)")


def check_duration(info: VideoInfo, storyboard: Storyboard) -> CheckResult:
    expected = storyboard.expected_duration
    in_limits = MIN_DURATION_SECONDS <= info.duration <= MAX_DURATION_SECONDS
    matches = abs(info.duration - expected) <= DURATION_TOLERANCE_SECONDS
    return _check(
        "duration", in_limits and matches,
        f"{info.duration:.2f} s (storyboard {expected:.2f} s ± {DURATION_TOLERANCE_SECONDS:g}, "
        f"limits {MIN_DURATION_SECONDS:g}–{MAX_DURATION_SECONDS:g} s)",
    )


def check_frames(info: VideoInfo) -> CheckResult:
    fractions = [float((frame.max(axis=2) > BLANK_PIXEL_THRESHOLD).mean()) for frame in info.sample_frames]
    ok = bool(fractions) and all(f >= MIN_CONTENT_FRACTION for f in fractions)
    shown = ", ".join(f"{f:.1%}" for f in fractions)
    return _check("frames_not_blank", ok, f"visible content in sampled frames: {shown}")


def check_math(storyboard: Storyboard) -> list[CheckResult]:
    fn = get_function(storyboard.function)
    x0 = storyboard.x0
    exact = fn.derivative(x0)
    numeric = numeric_derivative(fn, x0)
    tangent = tangent_line(fn, x0)
    start_error = abs(secant_slope(fn, x0, storyboard.h_start) - exact)
    end_error = abs(secant_slope(fn, x0, storyboard.h_end) - exact)
    expected_label = f"Tangent: {format_line_equation(tangent)}"
    return [
        _check("derivative",
               abs(storyboard.derivative - exact) <= MATH_TOLERANCE
               and abs(numeric - exact) <= MATH_TOLERANCE,
               f"f'({x0:g}) storyboard={storyboard.derivative:g}, exact={exact:g}, numeric={numeric:.6f}"),
        _check("tangent_line",
               abs(storyboard.tangent_intercept - tangent.intercept) <= MATH_TOLERANCE
               and abs(storyboard.y0 - fn.f(x0)) <= MATH_TOLERANCE
               and storyboard.tangent_label == expected_label,
               f"expected {expected_label}, storyboard says {storyboard.tangent_label!r} "
               f"(intercept {storyboard.tangent_intercept:g})"),
        _check("secant_converges",
               end_error < start_error and end_error <= SECANT_CONVERGENCE_TOLERANCE,
               f"|secant − f'| goes from {start_error:.4f} (h={storyboard.h_start:g}) "
               f"to {end_error:.4f} (h={storyboard.h_end:g})"),
    ]


def _fact_mismatches(storyboard: Storyboard, facts: RenderFacts) -> list[str]:
    problems = []
    close = lambda a, b: abs(a - b) <= DRAWN_TOLERANCE  # noqa: E731
    if not (close(facts.point[0], storyboard.x0) and close(facts.point[1], storyboard.y0)):
        problems.append(f"point P drawn at {facts.point}, expected ({storyboard.x0:g}, {storyboard.y0:g})")
    if not close(facts.tangent_slope, storyboard.derivative):
        problems.append(f"tangent slope drawn {facts.tangent_slope:.4f}, expected {storyboard.derivative:g}")
    if not close(facts.tangent_intercept, storyboard.tangent_intercept):
        problems.append(f"tangent intercept drawn {facts.tangent_intercept:.4f}")
    if not close(facts.final_h, storyboard.h_end):
        problems.append(f"final h {facts.final_h:g}, expected {storyboard.h_end:g}")
    expected_labels = {storyboard.function_label, storyboard.point_label,
                       storyboard.secant_slope_label, storyboard.tangent_label}
    missing = expected_labels - set(facts.labels)
    if missing:
        problems.append(f"missing labels: {sorted(missing)}")
    return problems


def check_rendered_values(storyboard: Storyboard, facts_path: Path) -> CheckResult:
    if not facts_path.is_file():
        return _check("rendered_values", False, f"{facts_path.name} not found")
    try:
        facts = RenderFacts.model_validate_json(facts_path.read_text(encoding="utf-8"))
    except ValidationError as error:
        return _check("rendered_values", False, f"{facts_path.name} is invalid: {error}")
    problems = _fact_mismatches(storyboard, facts)
    detail = "; ".join(problems) or "drawn point, tangent, final h and labels match the storyboard"
    return _check("rendered_values", not problems, detail)


def run_quality_checks(video: Path, storyboard: Storyboard, facts_path: Path) -> QAReport:
    checks = [check_video_file(video)]
    decode_check, info = inspect_video(video)
    checks.append(decode_check)
    if info is None:
        skipped = "skipped: video could not be decoded"
        checks += [_check(name, False, skipped) for name in ("resolution", "duration", "frames_not_blank")]
    else:
        checks += [check_resolution(info), check_duration(info, storyboard), check_frames(info)]
    checks += check_math(storyboard)
    checks.append(check_rendered_values(storyboard, facts_path))
    passed = all(check.status == "pass" for check in checks)
    return QAReport(passed=passed, video=video.name, checks=tuple(checks))


def run(paths: ProjectPaths) -> None:
    storyboard = read_model(paths.storyboard, Storyboard)
    report = run_quality_checks(paths.video, storyboard, paths.render_facts)
    report = report.model_copy(update={"video": paths.relative(paths.video)})
    write_model(paths.qa_report, report)
    if not report.passed:
        failed = [c.name for c in report.checks if c.status != "pass"]
        raise StageError(f"Quality checks failed: {', '.join(failed)}. See {paths.qa_report}")


def validate(paths: ProjectPaths) -> None:
    if not read_model(paths.qa_report, QAReport).passed:
        raise StageError("qa_report.json records failed checks")
