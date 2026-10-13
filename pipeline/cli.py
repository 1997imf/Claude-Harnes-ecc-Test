"""Command-line interface: run, status, resume.

Exit codes: 0 success, 1 a stage failed, 2 bad usage or missing input.
"""

import argparse
import sys
from pathlib import Path

from pipeline import __version__
from pipeline.manifest import ManifestError, load_manifest
from pipeline.paths import ProjectPaths
from pipeline.runner import describe_stages, run_pipeline
from pipeline.stages import DEFAULT_STAGES

EXIT_OK = 0
EXIT_STAGE_FAILED = 1
EXIT_USAGE = 2

DESCRIPTION = (
    "AI-assisted educational video pipeline: brief.json -> storyboard -> Manim render "
    "-> quality checks -> preview.html"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m pipeline", description=DESCRIPTION)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", metavar="{run,status,resume}")

    run = commands.add_parser("run", help="run every stage; skip ones that are still up to date")
    run.add_argument("brief", type=Path, help="path to brief.json")
    run.add_argument("--force", action="store_true", help="rerun every stage")

    status = commands.add_parser("status", help="show which stages completed, failed, or are pending")
    status.add_argument("project_dir", type=Path, help="project folder containing manifest.json")

    resume = commands.add_parser("resume", help="continue an earlier run, rerunning failed/outdated stages")
    resume.add_argument("brief", type=Path, help="path to brief.json")
    return parser


def _error(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)


def _run(brief: Path, *, force: bool, require_manifest: bool) -> int:
    if not brief.is_file():
        _error(f"Brief file not found: {brief}")
        return EXIT_USAGE
    paths = ProjectPaths.from_brief(brief)
    try:
        if require_manifest and load_manifest(paths.manifest) is None:
            _error(f"Nothing to resume in {paths.project_dir}. Start with: python -m pipeline run {brief}")
            return EXIT_USAGE
        result = run_pipeline(paths, DEFAULT_STAGES, force=force)
    except ManifestError as error:
        _error(str(error))
        return EXIT_USAGE
    if not result.succeeded:
        _error(f"stage '{result.failed_stage}' failed:\n{result.error}")
        print(f"Fix the problem, then run: python -m pipeline resume {brief}", file=sys.stderr)
        return EXIT_STAGE_FAILED
    print(f"\nDone. Video: {paths.video}\nPreview: {paths.preview}")
    return EXIT_OK


def _status(project_dir: Path) -> int:
    paths = ProjectPaths.from_project_dir(project_dir)
    try:
        if load_manifest(paths.manifest) is None:
            _error(f"No manifest in {paths.project_dir}; run the pipeline first")
            return EXIT_USAGE
        rows = describe_stages(paths, DEFAULT_STAGES)
    except ManifestError as error:
        _error(str(error))
        return EXIT_USAGE
    print(f"Project: {paths.project_dir}")
    for name, state, error in rows:
        line = f"  {name:<14} {state}"
        if state == "failed" and error:
            line += f" — {error.splitlines()[0]}"
        print(line)
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and return a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return _run(args.brief, force=args.force, require_manifest=False)
    if args.command == "resume":
        return _run(args.brief, force=False, require_manifest=True)
    if args.command == "status":
        return _status(args.project_dir)
    parser.print_help()
    return EXIT_OK
