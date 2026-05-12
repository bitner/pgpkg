from __future__ import annotations

from pathlib import Path

import pytest

from pgpkg.api import bundle_project, stage_version
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
    assert loaded.manifest.prefix == "sampleext"
    assert loaded.manifest.tracking_schema == "pgpkg"
    assert loaded.manifest.tracking_table == "migrations"
    assert loaded.manifest.version_source is None
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


def test_bundle_project_uses_project_root(sample_project: Path, tmp_path: Path):
    stage_version(sample_project, "0.1.0")

    out = tmp_path / "project-artifact.tar.zst"
    bundle_project(sample_project, out)

    loaded = load_artifact(out)
    assert loaded.manifest.project_name == "sampleext"
    assert "migrations/sampleext--0.1.0.sql" in loaded.migrations_files()


def test_artifact_manifest_preserves_runtime_config(sample_project: Path, tmp_path: Path):
    (sample_project / "pyproject.toml").write_text(
        "\n".join(
            [
                "[tool.pgpkg]",
                'project_name = "sampleext"',
                'prefix = "sampleext"',
                'version_source = "sampleext.migrate:VersionSource"',
                "",
                "[tool.pgpkg.tracking]",
                'schema = "sample_tracking"',
                'table = "schema_versions"',
            ]
        )
    )
    stage_version(sample_project, "0.1.0")

    out = tmp_path / "project-artifact.tar.zst"
    bundle_project(sample_project, out)

    loaded = load_artifact(out)
    assert loaded.manifest.tracking_schema == "sample_tracking"
    assert loaded.manifest.tracking_table == "schema_versions"
    assert loaded.manifest.version_source == "sampleext.migrate:VersionSource"


def test_build_artifact_is_deterministic(sample_project: Path, tmp_path: Path):
    stage_version(sample_project, "0.1.0")

    first = tmp_path / "first.tar.zst"
    second = tmp_path / "second.tar.zst"

    build_artifact(load_config(sample_project), first)
    build_artifact(load_config(sample_project), second)

    assert first.read_bytes() == second.read_bytes()


def test_bundle_project_rejects_invalid_migration_filenames(
    sample_project: Path,
    tmp_path: Path,
):
    migrations_dir = sample_project / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "sampleext.0.1.0.sql").write_text("-- invalid name\n")

    with pytest.raises(PgpkgError):
        bundle_project(sample_project, tmp_path / "invalid-artifact.tar.zst")
