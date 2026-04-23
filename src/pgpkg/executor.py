"""Apply migrations to a live database."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .catalog import Catalog
from .config import ProjectConfig
from .errors import ExecutionError
from .planner import MigrationPlan, plan
from .tracking import (
    acquire_advisory_lock,
    current_version,
    ensure_tracking,
    record_applied,
    sha256_text,
)
from .versioning import default_target

if TYPE_CHECKING:
    import psycopg


@dataclass
class ApplyResult:
    """What `apply_plan` did."""

    bootstrapped_from: str | None = None
    applied_steps: list[tuple[str, str]] = field(default_factory=list)  # (from, to) per step
    final_version: str | None = None

    @property
    def applied(self) -> list[str]:
        """Ordered list of versions newly present in the DB as a result of this apply.

        Includes the bootstrap version (if any) followed by each incremental target.
        """
        out: list[str] = []
        if self.bootstrapped_from is not None:
            out.append(self.bootstrapped_from)
        out.extend(to_v for _, to_v in self.applied_steps)
        return out


def apply_plan(
    conn: psycopg.Connection,
    config: ProjectConfig,
    catalog: Catalog,
    plan_obj: MigrationPlan,
    *,
    pre_sql: str = "",
    post_sql: str = "",
    dry_run: bool = False,
) -> ApplyResult:
    """Apply a precomputed plan inside a single transaction with an advisory lock.

    The connection's autocommit MUST be False (default for psycopg). The function
    will COMMIT on success or ROLLBACK on failure. If `dry_run` is True, all SQL
    is executed against the same transaction but rolled back at the end.
    """
    if conn.autocommit:
        raise ExecutionError("apply_plan requires conn.autocommit = False")

    result = ApplyResult()
    schema = config.tracking_schema
    table = config.tracking_table

    try:
        acquire_advisory_lock(conn, config.project_name)
        ensure_tracking(conn, schema=schema, table=table)

        # Re-check the live version inside the locked txn, in case it changed.
        live_version = current_version(conn, schema=schema, table=table)

        with conn.cursor() as cur:
            # Bootstrap if requested by the plan AND nothing is installed.
            if plan_obj.bootstrap_base is not None and live_version is None:
                base_sql = plan_obj.bootstrap_base.read_text(encoding="utf-8")
                _execute_step(cur, pre_sql, base_sql, post_sql)
                # Determine the version recorded for this bootstrap.
                # The base file IS for `target` if target is in catalog.base_files,
                # otherwise it's for the highest reachable base.
                bootstrap_version = _infer_bootstrap_version(catalog, plan_obj)
                record_applied(
                    conn,
                    bootstrap_version,
                    sha256_text(base_sql),
                    plan_obj.bootstrap_base.name,
                    schema=schema,
                    table=table,
                )
                result.bootstrapped_from = bootstrap_version
                result.final_version = bootstrap_version
            elif plan_obj.bootstrap_base is not None and live_version is not None:
                # The plan said to bootstrap but the DB already has a version installed.
                # Skip the bootstrap silently — we'll walk incrementals from the live version.
                pass

            for step in plan_obj.steps:
                inc_sql = step.file.read_text(encoding="utf-8")
                _execute_step(cur, pre_sql, inc_sql, post_sql)
                record_applied(
                    conn,
                    step.to_version,
                    sha256_text(inc_sql),
                    step.file.name,
                    schema=schema,
                    table=table,
                )
                result.applied_steps.append((step.from_version, step.to_version))
                result.final_version = step.to_version

        if dry_run:
            conn.rollback()
        else:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    return result


def _execute_step(
    cur,
    pre_sql: str,
    body_sql: str,
    post_sql: str,  # type: ignore[no-untyped-def]
) -> None:
    if pre_sql.strip():
        cur.execute(pre_sql)
    cur.execute(body_sql)
    if post_sql.strip():
        cur.execute(post_sql)


def _infer_bootstrap_version(catalog: Catalog, plan_obj: MigrationPlan) -> str:
    """The bootstrap base file's version, derived from its filename."""
    base_path = plan_obj.bootstrap_base
    assert base_path is not None
    for v, p in catalog.base_files.items():
        if p == base_path:
            return v
    raise ExecutionError(f"Bootstrap base file {base_path} not found in catalog")


def make_default_plan(
    catalog: Catalog,
    *,
    live_version: str | None,
    target: str | None = None,
) -> MigrationPlan:
    """Build a sensible default plan: target = unreleased if available else highest semver."""
    if target is None:
        target = default_target(catalog.versions)
    if target is None:
        raise ExecutionError(
            "No target version specified and the catalog is empty. "
            "Run `pgpkg stageversion <version>` first."
        )
    return plan(catalog, source=live_version, target=target)
