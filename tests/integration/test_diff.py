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


def test_makemigration_wraps_diff_with_files_and_sql(
    staged_project: Path,
    pg_url: str,
    tmp_path: Path,
):
    from pgpkg.api import stage_version

    (staged_project / "sql" / "030_newtable.sql").write_text(
        "CREATE TABLE IF NOT EXISTS sampleext.extra (id int PRIMARY KEY);\n"
    )
    stage_version(staged_project, "unreleased")

    prepend = tmp_path / "000_pre.sql"
    prepend.write_text("SET search_path TO sampleext, public;\n")
    append = tmp_path / "999_post.sql"
    append.write_text("SELECT 42;\n")

    path = generate_incremental(
        staged_project,
        from_version="0.2.0",
        to_version="unreleased",
        base_url=pg_url,
        prepend_files=[prepend],
        append_files=[append],
        append_sql=["SELECT 'done';"],
    )
    body = path.read_text()
    assert "SET search_path TO sampleext, public;" in body
    assert '"sampleext"."extra"' in body
    assert "SELECT 42;" in body
    assert "SELECT 'done';" in body


def test_makemigration_includes_body_only_function_changes(
    staged_project: Path,
    pg_url: str,
):
    from pgpkg.api import stage_version

    # Change only function body/signature internals without adding/removing objects.
    (staged_project / "sql" / "020_functions.sql").write_text(
        """CREATE OR REPLACE FUNCTION sampleext.item_count()
RETURNS bigint
LANGUAGE sql
AS $$
    SELECT count(*) + 1 FROM sampleext.items;
$$;
"""
    )
    stage_version(staged_project, "unreleased")

    path = generate_incremental(
        staged_project,
        from_version="0.2.0",
        to_version="unreleased",
        base_url=pg_url,
    )
    body = path.read_text().lower()
    assert "create or replace function sampleext.item_count()" in body
    assert "count(*) + 1" in body


def test_makemigration_includes_body_only_procedure_changes(
    staged_project: Path,
    pg_url: str,
):
    from pgpkg.api import stage_version

    (staged_project / "sql" / "020_functions.sql").write_text(
        """CREATE OR REPLACE PROCEDURE sampleext.refresh_items()
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM count(*) FROM sampleext.items;
END;
$$;
"""
    )
    stage_version(staged_project, "0.2.0")

    (staged_project / "sql" / "020_functions.sql").write_text(
        """CREATE OR REPLACE PROCEDURE sampleext.refresh_items()
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM count(*) + 1 FROM sampleext.items;
END;
$$;
"""
    )
    stage_version(staged_project, "unreleased")

    path = generate_incremental(
        staged_project,
        from_version="0.2.0",
        to_version="unreleased",
        base_url=pg_url,
    )
    body = path.read_text().lower()
    assert "create or replace procedure sampleext.refresh_items()" in body
    assert "count(*) + 1" in body
