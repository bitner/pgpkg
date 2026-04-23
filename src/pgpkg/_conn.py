"""Connection helper: builds a psycopg connection from kwargs/env, libpq-compatible."""

from __future__ import annotations

from typing import Any

import psycopg


def connect(
    conninfo: str | None = None,
    *,
    host: str | None = None,
    port: int | str | None = None,
    dbname: str | None = None,
    user: str | None = None,
    password: str | None = None,
    autocommit: bool = False,
    **extra: Any,
) -> psycopg.Connection:
    """Open a psycopg connection.

    If `conninfo` is given, use it directly (it may itself be empty, in which case
    libpq env vars take over). Otherwise pass kwargs to psycopg, which will fill
    blanks from PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD/etc.
    """
    if conninfo:
        return psycopg.connect(conninfo, autocommit=autocommit, **extra)
    kwargs: dict[str, Any] = {}
    if host is not None:
        kwargs["host"] = host
    if port is not None:
        kwargs["port"] = int(port)
    if dbname is not None:
        kwargs["dbname"] = dbname
    if user is not None:
        kwargs["user"] = user
    if password is not None:
        kwargs["password"] = password
    kwargs.update(extra)
    return psycopg.connect(autocommit=autocommit, **kwargs)
