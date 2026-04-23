from __future__ import annotations

from pathlib import Path

import pytest

from pgpkg.errors import LayoutError
from pgpkg.layout import (
    BaseFilename,
    IncrementalFilename,
    base_filename,
    incremental_filename,
    parse_migration_filename,
    sorted_fragments,
)


def test_base_filename():
    assert base_filename("proj", "0.1.0") == "proj--0.1.0.sql"


def test_incremental_filename():
    assert incremental_filename("proj", "0.1.0", "0.2.0") == "proj--0.1.0--0.2.0.sql"


def test_parse_base():
    p = parse_migration_filename(Path("proj--0.1.0.sql"))
    assert isinstance(p, BaseFilename)
    assert p.version == "0.1.0"


def test_parse_incremental():
    p = parse_migration_filename(Path("proj--0.1.0--0.2.0.sql"))
    assert isinstance(p, IncrementalFilename)
    assert (p.from_version, p.to_version) == ("0.1.0", "0.2.0")


def test_parse_unreleased():
    p = parse_migration_filename(Path("proj--unreleased.sql"))
    assert isinstance(p, BaseFilename)
    assert p.version == "unreleased"
    p2 = parse_migration_filename(Path("proj--0.2.0--unreleased.sql"))
    assert isinstance(p2, IncrementalFilename)
    assert p2.to_version == "unreleased"


def test_parse_invalid():
    with pytest.raises(LayoutError):
        parse_migration_filename(Path("notaname.sql"))


def test_parse_bad_version():
    with pytest.raises(LayoutError):
        parse_migration_filename(Path("proj--not!valid.sql"))


def test_sorted_fragments_ignores_dirs(tmp_path: Path):
    (tmp_path / "010.sql").write_text("x")
    (tmp_path / "005.sql").write_text("x")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "nested.sql").write_text("x")
    result = sorted_fragments(tmp_path)
    names = [p.name for p in result]
    assert names == ["005.sql", "010.sql"]
