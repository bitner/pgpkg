from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from pgpkg._conn import connect
from pgpkg.wrapper import scaffold_wrapper

pytestmark = pytest.mark.integration


def _reset(pg_url: str) -> None:
    with connect(pg_url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("DROP SCHEMA IF EXISTS pgpkg CASCADE")
        cur.execute("DROP SCHEMA IF EXISTS sampleext CASCADE")


def test_wrapper_end_to_end(staged_project: Path, pg_url: str, tmp_path: Path):
    _reset(pg_url)
    # Ensure there's at least one staged version (the staged_project fixture does this).
    output = tmp_path / "wrapper"
    scaffold_wrapper(staged_project, output_dir=output, cli_name="sampleext-migrator")
    assert (output / "pyproject.toml").exists()
    assert (output / "src" / "sampleext_migrator" / "migrations.tar.zst").exists()
    assert (output / "src" / "sampleext_migrator" / "cli.py").exists()

    # Build the wheel in a dedicated venv using uv
    venv = tmp_path / "venv"
    subprocess.run(["uv", "venv", str(venv)], check=True, capture_output=True)
    py = venv / "bin" / "python"

    # Install pgpkg first so the wrapper's `pgpkg>=0.1` dep resolves from the local editable.
    subprocess.run(
        ["uv", "pip", "install", "--python", str(py), "-e", str(Path(__file__).parents[2])],
        check=True,
        capture_output=True,
    )
    # Now install the wrapper
    subprocess.run(
        ["uv", "pip", "install", "--python", str(py), "--no-deps", "-e", str(output)],
        check=True,
        capture_output=True,
    )

    # Invoke the wrapper CLI to do a migrate
    result = subprocess.run(
        [
            str(venv / "bin" / "sampleext-migrator"),
            "migrate",
            "--to",
            "0.2.0",
            "--dsn",
            pg_url,
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "final version: 0.2.0" in result.stdout

    # info subcommand works too
    info = subprocess.run(
        [str(venv / "bin" / "sampleext-migrator"), "info"],
        capture_output=True,
        text=True,
    )
    assert info.returncode == 0
    assert "sampleext" in info.stdout
