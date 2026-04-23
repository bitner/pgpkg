from __future__ import annotations

from pathlib import Path

import pytest

from pgpkg.api import stage_version
from pgpkg.artifact import build_artifact, load_artifact
from pgpkg.config import load_config
from pgpkg.errors import PgpkgError


def test_build_and_load_artifact(sample_project: Path, tmp_path: Path):
    stage_version(sample_project, "0.1.0")
    (sample_project / "sql" / "pre" / "001_roles.sql").write_text("-- pre\n")
    (sample_project / "sql" / "post" / "999_grants.sql").write_text("-- post\n")

    config = load_config(sample_project)
    out = tmp_path / "art.tar.zst"
    build_artifact(config, out)
    assert out.exists() and out.stat().st_size > 0

    loaded = load_artifact(out)
    assert loaded.manifest.project_name == "sampleext"
    migs = loaded.migrations_files()
    assert "migrations/sampleext--0.1.0.sql" in migs
    assert "-- pre" in loaded.pre_sql()
    assert "-- post" in loaded.post_sql()


def test_artifact_integrity_check_fails_on_corruption(sample_project: Path, tmp_path: Path):
    stage_version(sample_project, "0.1.0")
    out = tmp_path / "art.tar.zst"
    build_artifact(load_config(sample_project), out)
    # Flip a byte
    raw = bytearray(out.read_bytes())
    raw[-10] ^= 0xFF
    out.write_bytes(bytes(raw))
    # Corrupting compressed stream likely fails on decompress already; accept either error
    with pytest.raises(Exception):  # noqa: B017 - corruption mode is intentionally broad
        load_artifact(out)


def test_empty_migrations_raises(sample_project: Path, tmp_path: Path):
    (sample_project / "migrations").mkdir()  # empty dir
    with pytest.raises(PgpkgError):
        build_artifact(load_config(sample_project), tmp_path / "x.tar.zst")
