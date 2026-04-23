from __future__ import annotations

from pathlib import Path

import pytest

from pgpkg.catalog import build_catalog
from pgpkg.config import load_config
from pgpkg.errors import CatalogError


def _stage(project: Path, filename: str, body: str = "-- stub\n") -> None:
    mig = project / "migrations"
    mig.mkdir(exist_ok=True)
    (mig / filename).write_text(body)


def test_build_catalog_empty(sample_project: Path):
    c = build_catalog(load_config(sample_project))
    assert c.base_files == {}
    assert c.edges == []
    assert c.versions == []


def test_build_catalog_mixed(sample_project: Path):
    _stage(sample_project, "sampleext--0.1.0.sql")
    _stage(sample_project, "sampleext--0.2.0.sql")
    _stage(sample_project, "sampleext--0.1.0--0.2.0.sql")
    _stage(sample_project, "sampleext--unreleased.sql")
    _stage(sample_project, "sampleext--0.2.0--unreleased.sql")
    c = build_catalog(load_config(sample_project))
    assert set(c.base_files) == {"0.1.0", "0.2.0", "unreleased"}
    assert {(f, t) for f, t, _ in c.edges} == {("0.1.0", "0.2.0"), ("0.2.0", "unreleased")}
    assert c.versions == ["0.1.0", "0.2.0", "unreleased"]


def test_catalog_wrong_prefix(sample_project: Path):
    _stage(sample_project, "otherproj--0.1.0.sql")
    with pytest.raises(CatalogError):
        build_catalog(load_config(sample_project))


def test_catalog_duplicate_base(sample_project: Path):
    _stage(sample_project, "sampleext--0.1.0.sql")
    # Same version via different (impossible) filename: craft one via direct write
    # Since filenames are unique, duplicate base is only possible if there's a bug.
    # We don't have a way to construct two files with the same version via valid names.
    # So just check self-loop detection instead:
    _stage(sample_project, "sampleext--0.1.0--0.1.0.sql")
    with pytest.raises(CatalogError):
        build_catalog(load_config(sample_project))


def test_catalog_bad_filename_ignored(sample_project: Path):
    mig = sample_project / "migrations"
    mig.mkdir(exist_ok=True)
    (mig / "README.md").write_text("hi")  # non-sql, ignored
    _stage(sample_project, "sampleext--0.1.0.sql")
    c = build_catalog(load_config(sample_project))
    assert list(c.base_files) == ["0.1.0"]
