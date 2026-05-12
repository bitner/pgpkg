"""makemigration: diff two staged versions via `results.temporary_local_db`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from .config import ProjectConfig
from .errors import PgpkgError
from .layout import incremental_filename


@dataclass(frozen=True)
class IncrementalResult:
    from_version: str
    to_version: str
    sql: str
    path: Path | None  # None if not written


def generate_incremental_sql(
    config: ProjectConfig,
    *,
    from_version: str,
    to_version: str,
    base_url: str = "postgresql:///postgres",
) -> str:
    """Build an incremental migration SQL by diffing two staged base files.

    Spins up two throwaway databases via `results.temporary_local_db(base_url)`,
    loads the staged base SQL for each version, and returns
    `db_from.schemadiff_as_sql(db_to)` — i.e. the SQL needed to transform `from`
    into `to`. Returns the bare diff SQL (no header). Empty string if identical.
    """
    try:
        from results.tempdb import temporary_local_db  # noqa: F401
    except ImportError as exc:  # pragma: no cover
        raise PgpkgError(
            "results library not installed. Add the 'diff' extra: pip install pgpkg[diff]",
            code="E_DIFF",
        ) from exc

    from results.tempdb import temporary_local_db

    from_path = _staged_path(config, from_version)
    to_path = _staged_path(config, to_version)
    from_sql = from_path.read_text(encoding="utf-8")
    to_sql = to_path.read_text(encoding="utf-8")

    with temporary_local_db(base_url) as db_from, temporary_local_db(base_url) as db_to:
        with db_from.t() as t:
            t.execute(from_sql)
        with db_to.t() as t:
            t.execute(to_sql)
        diff_sql: str = db_from.schemadiff_as_sql(db_to)
        target_routine_sigs = _load_routine_signatures(db_to, config.prefix)
        diff_sql = _strip_unsafe_routine_drops(diff_sql, target_routine_sigs)
        routine_diff_sql = _changed_routine_replacements_sql(db_from, db_to, config.prefix)

    if routine_diff_sql.strip():
        if diff_sql.strip():
            diff_sql = f"{diff_sql.rstrip()}\n\n{routine_diff_sql.rstrip()}\n"
        else:
            diff_sql = f"{routine_diff_sql.rstrip()}\n"
    return diff_sql


def _changed_routine_replacements_sql(db_from: Any, db_to: Any, schema: str) -> str:
    """Return CREATE OR REPLACE SQL for routines whose bodies changed.

    `results.schemadiff_as_sql()` can miss body-only routine changes. Detect
    those by comparing `pg_get_functiondef` between the staged `from` and `to`
    databases and emit replacement definitions from `to`.
    """
    from_map = _load_routine_definitions(db_from, schema)
    to_map = _load_routine_definitions(db_to, schema)

    replacements: list[str] = []
    for key, to_def in sorted(to_map.items()):
        from_def = from_map.get(key)
        if from_def is None:
            continue
        if _normalize_sql(from_def) == _normalize_sql(to_def):
            continue
        replacements.append(f"{to_def.rstrip()}\n;")
    return "\n\n".join(replacements)


def _load_routine_definitions(db: Any, schema: str) -> dict[tuple[str, str, str, str], str]:
    schema_lit = schema.replace("'", "''")
    sql = f"""
        SELECT
            n.nspname,
            p.prokind,
            p.proname,
            pg_get_function_identity_arguments(p.oid) AS identity_args,
            pg_get_functiondef(p.oid) AS definition
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = '{schema_lit}'
          AND p.prokind IN ('f', 'p')
    """
    with db.t() as t:
        rows = t.execute(sql)

    out: dict[tuple[str, str, str, str], str] = {}
    for nspname, prokind, proname, identity_args, definition in rows:
        key = (str(nspname), str(prokind), str(proname), str(identity_args))
        out[key] = str(definition)
    return out


def _load_routine_signatures(db: Any, schema: str) -> set[tuple[str, str]]:
    schema_lit = schema.replace("'", "''")
    sql = f"""
        SELECT
            CASE p.prokind
                WHEN 'p' THEN 'procedure'
                ELSE 'function'
            END,
            n.nspname || '.' || p.proname || '(' || oidvectortypes(p.proargtypes) || ')'
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = '{schema_lit}'
          AND p.prokind IN ('f', 'p')
    """
    with db.t() as t:
        rows = t.execute(sql)
    return {
        (_normalize_routine_kind(str(kind)), _normalize_signature_text(str(sig)))
        for kind, sig in rows
    }


def _strip_unsafe_routine_drops(
    diff_sql: str, target_signatures: set[tuple[str, str]]
) -> str:
    """Remove DROP FUNCTION/PROCEDURE statements for routines still in target.

    Some diffs emit a DROP for a routine that is still present in the target
    schema (typically a body-only or property-only change). That can fail when
    other objects depend on the routine; `CREATE OR REPLACE` is the safe path.
    """
    if not diff_sql.strip():
        return diff_sql

    out_lines: list[str] = []
    drop_re = re.compile(
        r"^\s*drop\s+(function|procedure)\s+if\s+exists\s+(.+?)\s*;\s*$",
        re.IGNORECASE,
    )

    for line in diff_sql.splitlines():
        m = drop_re.match(line)
        if m:
            target_key = (
                _normalize_routine_kind(m.group(1)),
                _normalize_signature_text(m.group(2)),
            )
            if target_key in target_signatures:
                continue
        out_lines.append(line)
    return "\n".join(out_lines)


def _normalize_routine_kind(kind: str) -> str:
    return kind.strip().lower()


def _normalize_signature_text(sig: str) -> str:
    s = sig.replace('"', "").strip()
    s = re.sub(r"\s*,\s*", ",", s)
    s = re.sub(r"\(\s*", "(", s)
    s = re.sub(r"\s*\)", ")", s)
    s = re.sub(r"\s+", " ", s)
    return s


def _normalize_sql(sql: str) -> str:
    return "\n".join(line.rstrip() for line in sql.strip().splitlines())


def write_incremental(
    config: ProjectConfig,
    *,
    from_version: str,
    to_version: str,
    base_url: str = "postgresql:///postgres",
    output_path: Path | None = None,
    overwrite: bool = True,
    prepend_files: list[Path] | None = None,
    append_files: list[Path] | None = None,
    append_sql: list[str] | None = None,
) -> IncrementalResult:
    """Generate and write an incremental migration file."""
    diff_sql = generate_incremental_sql(
        config, from_version=from_version, to_version=to_version, base_url=base_url
    )
    target = output_path or (
        config.migrations_dir / incremental_filename(config.prefix, from_version, to_version)
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not overwrite:
        raise PgpkgError(f"{target} already exists and overwrite=False", code="E_DIFF")
    body = _render_incremental_body(
        config=config,
        from_version=from_version,
        to_version=to_version,
        diff_sql=diff_sql,
        prepend_files=prepend_files or [],
        append_files=append_files or [],
        append_sql=append_sql or [],
    )
    if not body.endswith("\n"):
        body += "\n"
    target.write_text(body, encoding="utf-8")
    return IncrementalResult(
        from_version=from_version, to_version=to_version, sql=diff_sql, path=target
    )


def _render_incremental_body(
    *,
    config: ProjectConfig,
    from_version: str,
    to_version: str,
    diff_sql: str,
    prepend_files: list[Path],
    append_files: list[Path],
    append_sql: list[str],
) -> str:
    parts = [
        "-- Generated by pgpkg makemigration",
        f"-- Project: {config.project_name}",
        f"-- From:    {from_version}",
        f"-- To:      {to_version}",
        "-- Review the diff before applying.",
        "",
    ]
    parts.extend(_read_sql_block(path) for path in prepend_files)
    if diff_sql.strip():
        parts.append(diff_sql.rstrip("\n"))
    parts.extend(_read_sql_block(path) for path in append_files)
    parts.extend(sql.rstrip("\n") for sql in append_sql if sql.strip())
    return "\n".join(parts)


def _read_sql_block(path: Path) -> str:
    if not path.is_file():
        raise PgpkgError(f"SQL wrapper file not found: {path}", code="E_DIFF")
    return path.read_text(encoding="utf-8").rstrip("\n")


def _staged_path(config: ProjectConfig, version: str) -> Path:
    from .layout import base_filename

    p = config.migrations_dir / base_filename(config.prefix, version)
    if not p.is_file():
        raise PgpkgError(
            f"Staged base file for version {version!r} not found at {p}. "
            f"Run `pgpkg stageversion {version}` first.",
            code="E_DIFF",
        )
    return p
