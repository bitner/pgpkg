from __future__ import annotations

from pathlib import Path

import pytest

from pgpkg.api import generate_incremental

pytestmark = pytest.mark.integration


def test_makemigration_produces_diff(staged_project: Path, pg_url: str):
    # Add a new column to sql/ so 0.2.0 -> unreleased produces a meaningful diff.
    (staged_project / "sql" / "030_newtable.sql").write_text(
        "CREATE TABLE IF NOT EXISTS sampleext.extra (id int PRIMARY KEY);\n"
    )
    from pgpkg.api import stage_version

    stage_version(staged_project, "unreleased")

    path = generate_incremental(
        staged_project,
        from_version="0.2.0",
        to_version="unreleased",
        base_url=pg_url,
    )
    body = path.read_text().lower()
    assert "extra" in body
    assert "create table" in body


def test_makemigration_empty_when_identical(staged_project: Path, pg_url: str):
    # 0.2.0 is what sql/ renders to right now (before modifications) — stage unreleased
    # from the same sql/ state, then diff: result should be empty/trivial.
    from pgpkg.api import stage_version

    stage_version(staged_project, "unreleased")
    path = generate_incremental(
        staged_project,
        from_version="0.2.0",
        to_version="unreleased",
        base_url=pg_url,
    )
    # Body contains header + (possibly empty) diff body. Strip comments.
    body = path.read_text()
    non_comment = "\n".join(
        line for line in body.splitlines() if line.strip() and not line.strip().startswith("--")
    ).strip()
    assert non_comment == ""
