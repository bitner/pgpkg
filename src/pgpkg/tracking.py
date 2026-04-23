"""Tracking schema: pgpkg.migrations + helpers to read/write installed version."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import psycopg


def tracking_ddl(schema: str = "pgpkg", table: str = "migrations") -> str:
    """Return the SQL to install the tracking schema/table (idempotent)."""
    return f"""
CREATE SCHEMA IF NOT EXISTS {schema};
CREATE TABLE IF NOT EXISTS {schema}.{table} (
    id          serial PRIMARY KEY,
    version     text NOT NULL,
    applied_at  timestamptz NOT NULL DEFAULT now(),
    sha256      text NOT NULL,
    filename    text NOT NULL
);
""".strip()


def ensure_tracking(conn: psycopg.Connection, *, schema: str = "pgpkg", table: str = "migrations") -> None:
    """Install the tracking schema/table if missing. Idempotent."""
    with conn.cursor() as cur:
        cur.execute(tracking_ddl(schema, table))


def current_version(
    conn: psycopg.Connection, *, schema: str = "pgpkg", table: str = "migrations"
) -> str | None:
    """Return the most recently applied version, or None if nothing applied."""
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT to_regclass('{schema}.{table}')"
        )
        exists = cur.fetchone()[0]
        if exists is None:
            return None
        cur.execute(f"SELECT version FROM {schema}.{table} ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        return row[0] if row else None


def record_applied(
    conn: psycopg.Connection,
    version: str,
    sha256: str,
    filename: str,
    *,
    schema: str = "pgpkg",
    table: str = "migrations",
) -> None:
    """Insert a row noting that `version` was just applied."""
    with conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO {schema}.{table} (version, sha256, filename) VALUES (%s, %s, %s)",
            (version, sha256, filename),
        )


def acquire_advisory_lock(conn: psycopg.Connection, project_name: str) -> None:
    """Acquire an xact-scoped advisory lock keyed deterministically on project_name."""
    digest = hashlib.sha256(project_name.encode("utf-8")).digest()
    # take first 8 bytes as signed int64
    key = int.from_bytes(digest[:8], "big", signed=True)
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(%s)", (key,))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
