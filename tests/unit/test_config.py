from __future__ import annotations

from pathlib import Path

import pytest

from pgpkg.config import load_config, load_project
from pgpkg.errors import ConfigError


def test_load_config_sample(sample_project: Path):
    c = load_config(sample_project)
    assert c.project_name == "sampleext"
    assert c.prefix == "sampleext"
    assert c.sql_dir == sample_project / "sql"
    assert c.migrations_dir == sample_project / "migrations"
    assert c.pre_dir == sample_project / "sql" / "pre"
    assert c.post_dir == sample_project / "sql" / "post"
    assert c.tracking_schema == "pgpkg"


def test_missing_pyproject(tmp_path: Path):
    with pytest.raises(ConfigError):
        load_config(tmp_path)


def test_missing_pgpkg_section(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = \"x\"\n")
    with pytest.raises(ConfigError):
        load_config(tmp_path)


def test_project_name_fallback_to_project(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "fallback"\n[tool.pgpkg]\n'
    )
    c = load_config(tmp_path)
    assert c.project_name == "fallback"
    assert c.prefix == "fallback"


def test_load_project_empty_migrations(sample_project: Path):
    project = load_project(sample_project)
    assert project.catalog.versions == []
