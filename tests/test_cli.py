"""Phase 0 acceptance tests for the pipeline command-line entry point."""

import subprocess
import sys
from pathlib import Path

import pytest

from pipeline import __version__, cli
from pipeline.cli import main
from pipeline.runner import Stage
from tests.conftest import write_brief

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_help_exits_successfully_and_describes_the_pipeline(capsys):
    # Arrange / Act
    with pytest.raises(SystemExit) as exit_info:
        main(["--help"])

    # Assert
    assert exit_info.value.code == 0
    assert "educational video pipeline" in capsys.readouterr().out


def test_version_flag_prints_package_version(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])

    assert exit_info.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_no_arguments_prints_help_and_returns_zero(capsys):
    exit_code = main([])

    assert exit_code == 0
    assert "usage:" in capsys.readouterr().out


def test_unknown_argument_exits_with_usage_error(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--no-such-flag"])

    assert exit_info.value.code == 2
    assert "unrecognized arguments" in capsys.readouterr().err


def test_python_dash_m_pipeline_help_runs_as_a_module():
    # Exercises pipeline/__main__.py exactly as a user would run it.
    result = subprocess.run(
        [sys.executable, "-m", "pipeline", "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0
    assert "usage:" in result.stdout


# --- Phase 1 commands -------------------------------------------------------


def _fake_stages():
    def write_done(paths):
        (paths.project_dir / "done.txt").write_text("ok")

    return (
        Stage(
            name="plan",
            inputs=lambda p: (p.brief,),
            outputs=lambda p: (p.project_dir / "done.txt",),
            run=write_done,
        ),
    )


@pytest.fixture
def fake_stages(monkeypatch):
    monkeypatch.setattr(cli, "DEFAULT_STAGES", _fake_stages())


def test_help_lists_run_status_and_resume_commands(capsys):
    with pytest.raises(SystemExit):
        main(["--help"])

    out = capsys.readouterr().out
    assert all(command in out for command in ("run", "status", "resume"))


def test_run_with_missing_brief_exits_2_with_message(tmp_path, capsys):
    exit_code = main(["run", str(tmp_path / "missing" / "brief.json")])

    assert exit_code == 2
    assert "not found" in capsys.readouterr().err


def test_run_with_invalid_brief_exits_nonzero_and_explains(tmp_path, capsys):
    paths = write_brief(tmp_path / "bad", {"topic": "t", "function": "x**4", "x0": 1, "h_start": 1})

    exit_code = main(["run", str(paths.brief)])

    err = capsys.readouterr().err
    assert exit_code == 1
    assert "plan" in err and "Unsupported function 'x**4'" in err


def test_run_success_then_status(tmp_path, capsys, fake_stages):
    paths = write_brief(tmp_path / "proj")

    assert main(["run", str(paths.brief)]) == 0
    assert main(["status", str(paths.project_dir)]) == 0

    out = capsys.readouterr().out
    assert "plan" in out and "completed" in out


def test_status_without_manifest_exits_2(tmp_path, capsys):
    assert main(["status", str(tmp_path)]) == 2
    assert "No manifest" in capsys.readouterr().err


def test_status_with_corrupt_manifest_exits_2(tmp_path, capsys):
    (tmp_path / "manifest.json").write_text("{oops")

    assert main(["status", str(tmp_path)]) == 2
    assert "manifest.json" in capsys.readouterr().err


def test_resume_requires_existing_manifest(tmp_path, capsys, fake_stages):
    paths = write_brief(tmp_path / "proj")

    assert main(["resume", str(paths.brief)]) == 2
    assert "pipeline run" in capsys.readouterr().err


def test_resume_skips_completed_stages(tmp_path, capsys, fake_stages):
    paths = write_brief(tmp_path / "proj")
    main(["run", str(paths.brief)])

    assert main(["resume", str(paths.brief)]) == 0
    assert "up to date" in capsys.readouterr().out


def test_run_force_reruns_completed_stages(tmp_path, capsys, fake_stages):
    paths = write_brief(tmp_path / "proj")
    main(["run", str(paths.brief)])
    capsys.readouterr()

    assert main(["run", "--force", str(paths.brief)]) == 0
    assert "plan: running" in capsys.readouterr().out
