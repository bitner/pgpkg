from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pgpkg.cli", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def test_top_level_help():
    cp = _run("--help")
    assert cp.returncode == 0
    assert "stageversion" in cp.stdout
    assert "makemigration" in cp.stdout
    assert "migrate" in cp.stdout
    assert "wheel" in cp.stdout


def test_info_sample_project(sample_project: Path):
    cp = _run("info", "--project-root", str(sample_project))
    assert cp.returncode == 0
    assert "sampleext" in cp.stdout


def test_versions_empty(sample_project: Path):
    cp = _run("versions", "--project-root", str(sample_project))
    assert cp.returncode == 0


def test_stageversion(sample_project: Path):
    cp = _run(
        "stageversion", "0.1.0", "--project-root", str(sample_project)
    )
    assert cp.returncode == 0, cp.stderr
    assert (sample_project / "migrations" / "sampleext--0.1.0.sql").exists()


def test_graph_text(staged_project: Path):
    cp = _run("graph", "--project-root", str(staged_project))
    assert cp.returncode == 0
    assert "0.1.0" in cp.stdout


def test_graph_dot(staged_project: Path):
    cp = _run("graph", "--format", "dot", "--project-root", str(staged_project))
    assert cp.returncode == 0
    assert "digraph" in cp.stdout


def test_plan_command(staged_project: Path):
    cp = _run(
        "plan",
        "--source",
        "0.1.0",
        "--to",
        "0.2.0",
        "--project-root",
        str(staged_project),
    )
    assert cp.returncode == 0, cp.stderr
    assert "0.1.0" in cp.stdout and "0.2.0" in cp.stdout
