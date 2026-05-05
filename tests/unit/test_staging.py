from __future__ import annotations

from pathlib import Path

import pytest

from pgpkg.api import list_versions, stage_version
from pgpkg.config import load_config
from pgpkg.errors import LayoutError
from pgpkg.staging import read_pre_post, render_staged_sql


def test_render_includes_fragments(sample_project: Path):
    sql = render_staged_sql(load_config(sample_project), "0.1.0")
    assert "-- BEGIN FRAGMENT: 010_schema.sql" in sql
    assert "-- BEGIN FRAGMENT: 020_functions.sql" in sql
    assert "CREATE SCHEMA IF NOT EXISTS sampleext;" in sql
    assert "Version: 0.1.0" in sql


def test_stage_version_writes_file(sample_project: Path):
    path = stage_version(sample_project, "0.1.0")
    assert path.exists()
    assert path.name == "sampleext--0.1.0.sql"
    assert "Version: 0.1.0" in path.read_text()


def test_stage_version_also_writes_second_copy(sample_project: Path, tmp_path: Path):
    extra = tmp_path / "sampleext.sql"
    path = stage_version(sample_project, "0.1.0", also_write=extra)
    assert path.exists()
    assert extra.exists()
    assert extra.read_text() == path.read_text()


def test_stage_version_also_write_preflights_all_targets(sample_project: Path, tmp_path: Path):
    extra = tmp_path / "sampleext.sql"
    extra.write_text("existing")

    with pytest.raises(LayoutError):
        stage_version(sample_project, "0.1.0", also_write=extra, overwrite=False)

    assert not (sample_project / "migrations" / "sampleext--0.1.0.sql").exists()


def test_no_sql_dir(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text('[tool.pgpkg]\nproject_name = "x"\n')
    with pytest.raises(LayoutError):
        render_staged_sql(load_config(tmp_path), "0.1.0")


def test_no_fragments(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text('[tool.pgpkg]\nproject_name = "x"\n')
    (tmp_path / "sql").mkdir()
    with pytest.raises(LayoutError):
        render_staged_sql(load_config(tmp_path), "0.1.0")


def test_read_pre_post_empty(sample_project: Path):
    pre, post = read_pre_post(load_config(sample_project))
    assert pre == ""
    assert post == ""


def test_read_pre_post_with_files(sample_project: Path):
    (sample_project / "sql" / "pre" / "001_a.sql").write_text("SELECT 1;")
    (sample_project / "sql" / "post" / "001_z.sql").write_text("SELECT 2;")
    pre, post = read_pre_post(load_config(sample_project))
    assert "SELECT 1;" in pre
    assert "SELECT 2;" in post


def test_list_versions_after_stage(sample_project: Path):
    stage_version(sample_project, "0.1.0")
    assert list_versions(sample_project) == ["0.1.0"]
