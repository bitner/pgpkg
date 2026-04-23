from __future__ import annotations

from pathlib import Path

import pytest

from pgpkg._conn import connect
from pgpkg.api import apply_migrations, migrate, verify_round_trip

pytestmark = pytest.mark.integration


def _drop_everything(pg_url: str) -> None:
    with connect(pg_url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("DROP SCHEMA IF EXISTS pgpkg CASCADE")
        cur.execute("DROP SCHEMA IF EXISTS sampleext CASCADE")


def test_fresh_install_then_incremental(staged_project: Path, pg_url: str):
    _drop_everything(pg_url)
    result = apply_migrations(staged_project, target="0.1.0", conninfo=pg_url)
    assert result.applied == ["0.1.0"]
    with connect(pg_url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT version FROM pgpkg.migrations ORDER BY id")
        assert [r[0] for r in cur.fetchall()] == ["0.1.0"]

    result = apply_migrations(staged_project, target="0.2.0", conninfo=pg_url)
    assert result.applied == ["0.2.0"]
    with connect(pg_url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT version FROM pgpkg.migrations ORDER BY id")
        assert [r[0] for r in cur.fetchall()] == ["0.1.0", "0.2.0"]


def test_migrate_alias(staged_project: Path, pg_url: str):
    _drop_everything(pg_url)
    result = migrate(staged_project, target="0.2.0", conninfo=pg_url)
    assert "0.2.0" in result.applied


def test_idempotent_when_already_at_target(staged_project: Path, pg_url: str):
    _drop_everything(pg_url)
    migrate(staged_project, target="0.1.0", conninfo=pg_url)
    result = migrate(staged_project, target="0.1.0", conninfo=pg_url)
    assert result.applied == []


def test_verify_round_trip_passes(staged_project: Path, pg_url: str):
    # verify_round_trip uses results.temporary_local_db, which needs an admin URL.
    problems = verify_round_trip(staged_project, base_url=pg_url)
    # Our hand-crafted incremental is exactly equivalent to the 0.2.0 base,
    # so there should be no diff.
    assert problems == []
