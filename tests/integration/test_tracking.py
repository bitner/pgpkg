from __future__ import annotations

import pytest

from pgpkg._conn import connect
from pgpkg.tracking import (
    acquire_advisory_lock,
    current_version,
    ensure_tracking,
    record_applied,
    sha256_text,
)

pytestmark = pytest.mark.integration


def _reset(pg_url: str) -> None:
    with connect(pg_url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("DROP SCHEMA IF EXISTS pgpkg CASCADE")


def test_ensure_tracking_idempotent(pg_url: str):
    _reset(pg_url)
    with connect(pg_url, autocommit=True) as conn:
        ensure_tracking(conn)
        ensure_tracking(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('pgpkg.migrations') IS NOT NULL")
            row = cur.fetchone()
            assert row is not None
            assert row[0] is True


def test_current_version_none_then_recorded(pg_url: str):
    _reset(pg_url)
    with connect(pg_url) as conn:
        ensure_tracking(conn)
        assert current_version(conn) is None
        record_applied(
            conn,
            version="0.1.0",
            filename="sampleext--0.1.0.sql",
            sha256=sha256_text("x"),
        )
        conn.commit()
        assert current_version(conn) == "0.1.0"
        record_applied(
            conn,
            version="0.2.0",
            filename="sampleext--0.1.0--0.2.0.sql",
            sha256=sha256_text("y"),
        )
        conn.commit()
        assert current_version(conn) == "0.2.0"


def test_advisory_lock(pg_url: str):
    with connect(pg_url) as conn:
        acquire_advisory_lock(conn, "myproj")
        conn.commit()
