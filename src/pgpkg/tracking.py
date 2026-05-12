"""Tracking schema: pgpkg.migrations + helpers to read/write installed version."""

from __future__ import annotations

import hashlib
import sys
from contextlib import contextmanager, suppress
from importlib import import_module
from typing import TYPE_CHECKING, Protocol, cast, runtime_checkable

import psycopg
from psycopg import sql

from .errors import ConfigError

if TYPE_CHECKING:
    from .config import ProjectConfig


def tracking_ddl(schema: str = "pgpkg", table: str = "migrations") -> sql.Composed:
    """Return the SQL to install the tracking schema/table (idempotent)."""
    schema_ident = sql.Identifier(schema)
    table_ident = sql.Identifier(table)
    return sql.SQL(
        "CREATE SCHEMA IF NOT EXISTS {schema};"
        "CREATE TABLE IF NOT EXISTS {schema}.{table} ("
        "id serial PRIMARY KEY, "
        "version text NOT NULL, "
        "applied_at timestamptz NOT NULL DEFAULT now(), "
        "sha256 text NOT NULL, "
        "filename text NOT NULL"
        ");"
    ).format(schema=schema_ident, table=table_ident)


@contextmanager
def _session_role(conn: psycopg.Connection):
    """Temporarily reset to the session user when SQL changed the effective role.

    Some migration frameworks intentionally `SET ROLE` during apply. pgpkg's
    tracking writes should still run as the original session user that started
    the migration transaction.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT session_user, current_user")
        row = cur.fetchone()

    if row is None:
        yield
        return

    session_user, current_user = row
    if session_user == current_user:
        yield
        return

    with conn.cursor() as cur:
        cur.execute("RESET ROLE")

    try:
        yield
    finally:
        with conn.cursor() as cur:
            cur.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(current_user)))


def ensure_tracking(
    conn: psycopg.Connection, *, schema: str = "pgpkg", table: str = "migrations"
) -> None:
    """Install the tracking schema/table if missing. Idempotent."""
    with _session_role(conn), conn.cursor() as cur:
        cur.execute(tracking_ddl(schema, table))


def current_tracking_version(
    conn: psycopg.Connection, *, schema: str = "pgpkg", table: str = "migrations"
) -> str | None:
    """Return the most recently applied version, or None if nothing applied."""
    with _session_role(conn), conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s)", (f"{schema}.{table}",))
        exists_row = cur.fetchone()
        if exists_row is None:
            return None
        exists = exists_row[0]
        if exists is None:
            return None
        cur.execute(
            sql.SQL(
                "SELECT version FROM {schema}.{table} ORDER BY id DESC LIMIT 1"
            ).format(
                schema=sql.Identifier(schema),
                table=sql.Identifier(table),
            )
        )
        row = cur.fetchone()
        return row[0] if row else None


def record_tracking_applied(
    conn: psycopg.Connection,
    version: str,
    sha256: str,
    filename: str,
    *,
    schema: str = "pgpkg",
    table: str = "migrations",
) -> None:
    """Insert a row noting that `version` was just applied."""
    with _session_role(conn), conn.cursor() as cur:
        cur.execute(
            sql.SQL(
                "INSERT INTO {schema}.{table} (version, sha256, filename) VALUES (%s, %s, %s)"
            ).format(
                schema=sql.Identifier(schema),
                table=sql.Identifier(table),
            ),
            (version, sha256, filename),
        )


current_version = current_tracking_version
record_applied = record_tracking_applied


@runtime_checkable
class VersionSource(Protocol):
    """Read the user-visible installed version and record successful applies."""

    def read_live_version(
        self,
        conn: psycopg.Connection,
        config: ProjectConfig,
    ) -> str | None: ...

    def record_applied(
        self,
        conn: psycopg.Connection,
        config: ProjectConfig,
        *,
        version: str,
        sha256: str,
        filename: str,
    ) -> None: ...


class DefaultVersionSource:
    """Use pgpkg's own tracking table as the authoritative installed version."""

    writes_default_tracking = True

    def read_live_version(
        self,
        conn: psycopg.Connection,
        config: ProjectConfig,
    ) -> str | None:
        return current_tracking_version(
            conn,
            schema=config.tracking_schema,
            table=config.tracking_table,
        )

    def record_applied(
        self,
        conn: psycopg.Connection,
        config: ProjectConfig,
        *,
        version: str,
        sha256: str,
        filename: str,
    ) -> None:
        record_tracking_applied(
            conn,
            version=version,
            sha256=sha256,
            filename=filename,
            schema=config.tracking_schema,
            table=config.tracking_table,
        )


@contextmanager
def _project_import_path(project_root):  # type: ignore[no-untyped-def]
    path = str(project_root)
    added = False
    if path and path not in sys.path:
        sys.path.insert(0, path)
        added = True
    try:
        yield
    finally:
        if added:
            with suppress(ValueError):
                sys.path.remove(path)


def resolve_version_source(
    config: ProjectConfig,
    override: VersionSource | None = None,
) -> VersionSource:
    """Return the configured version source instance.

    `override` wins over `[tool.pgpkg].version_source`. The configured string must
    use `module:attribute` syntax and resolve to either an instance or a zero-arg
    class that implements the VersionSource protocol.
    """
    if override is not None:
        return _validate_version_source_instance(override)

    if config.version_source is None:
        return DefaultVersionSource()

    module_name, sep, attr_name = config.version_source.partition(":")
    if not sep or not module_name or not attr_name:
        raise ConfigError(
            "[tool.pgpkg].version_source must use 'module:attribute' syntax."
        )

    try:
        with _project_import_path(config.project_root):
            module = import_module(module_name)
    except Exception as exc:
        raise ConfigError(
            f"Could not import version source module {module_name!r} from project root "
            f"{config.project_root}: {exc}. Install the module in the runtime environment "
            "or pass version_source=... explicitly."
        ) from exc

    try:
        source_obj = getattr(module, attr_name)
    except AttributeError as exc:
        raise ConfigError(
            f"Version source attribute {attr_name!r} not found in module {module_name!r}."
        ) from exc

    if isinstance(source_obj, type):
        source_obj = source_obj()

    return _validate_version_source_instance(source_obj)


def _validate_version_source_instance(source: object) -> VersionSource:
    missing = [
        attr
        for attr in ("read_live_version", "record_applied")
        if not callable(getattr(source, attr, None))
    ]
    if missing:
        missing_str = ", ".join(missing)
        raise ConfigError(
            f"Configured version source is missing required callable(s): {missing_str}."
        )
    return cast(VersionSource, source)


def acquire_advisory_lock(conn: psycopg.Connection, project_name: str) -> None:
    """Acquire an xact-scoped advisory lock keyed deterministically on project_name."""
    digest = hashlib.sha256(project_name.encode("utf-8")).digest()
    # take first 8 bytes as signed int64
    key = int.from_bytes(digest[:8], "big", signed=True)
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(%s)", (key,))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
