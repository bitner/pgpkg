"""Stable Python facade. Designed for use both from the CLI and from wrappers."""

from __future__ import annotations

import atexit
import shutil
from pathlib import Path

from psycopg import sql

from . import _conn
from .artifact import LoadedArtifact, build_artifact, load_artifact
from .catalog import Catalog, build_catalog
from .config import Project, ProjectConfig, load_config, load_project
from .diff import write_incremental
from .errors import PgpkgError
from .executor import ApplyResult, apply_plan, make_default_plan
from .planner import MigrationPlan, plan, render_graph_dot, render_graph_text
from .staging import read_pre_post, write_staged_file

__all__ = [
    "PgpkgError",
    "Project",
    "ProjectConfig",
    "load_config",
    "load_project",
    "list_versions",
    "stage_version",
    "generate_incremental",
    "plan_path",
    "render_graph",
    "apply_migrations",
    "migrate",
    "verify_round_trip",
    "build_artifact",
    "load_artifact",
    "migrate_from_artifact",
]


def list_versions(project_root: str | Path) -> list[str]:
    """Return all known versions, sorted (released first, unreleased last)."""
    project = load_project(project_root)
    return project.catalog.versions


def stage_version(
    project_root: str | Path,
    version: str,
    *,
    output_path: Path | None = None,
    overwrite: bool = True,
) -> Path:
    """Render and write `<prefix>--<version>.sql` from the project's sql/ tree."""
    config = load_config(project_root)
    return write_staged_file(config, version, output_path=output_path, overwrite=overwrite)


def generate_incremental(
    project_root: str | Path,
    *,
    from_version: str,
    to_version: str,
    base_url: str = "postgresql:///postgres",
    output_path: Path | None = None,
) -> Path:
    """Generate `<prefix>--<from>--<to>.sql` by diffing two staged base files."""
    config = load_config(project_root)
    res = write_incremental(
        config,
        from_version=from_version,
        to_version=to_version,
        base_url=base_url,
        output_path=output_path,
    )
    assert res.path is not None
    return res.path


def plan_path(
    project_root: str | Path,
    *,
    source: str | None,
    target: str,
) -> MigrationPlan:
    config = load_config(project_root)
    catalog = build_catalog(config)
    return plan(catalog, source=source, target=target)


def render_graph(project_root: str | Path, *, format: str = "text") -> str:
    project = load_project(project_root)
    if format == "dot":
        return render_graph_dot(project.catalog)
    return render_graph_text(project.catalog)


def apply_migrations(
    project_root: str | Path,
    *,
    target: str | None = None,
    dry_run: bool = False,
    conninfo: str | None = None,
    host: str | None = None,
    port: int | str | None = None,
    dbname: str | None = None,
    user: str | None = None,
    password: str | None = None,
) -> ApplyResult:
    """Apply migrations to a live DB. Mirrors `pgpkg.migrate` but uses project source tree."""
    project = load_project(project_root)
    return _migrate_with_catalog(
        project.config,
        project.catalog,
        pre_post=read_pre_post(project.config),
        target=target,
        dry_run=dry_run,
        conninfo=conninfo,
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
    )


# Friendly alias matching the promised public name in __init__
migrate = apply_migrations


def migrate_from_artifact(
    artifact_path: str | Path,
    *,
    target: str | None = None,
    dry_run: bool = False,
    conninfo: str | None = None,
    host: str | None = None,
    port: int | str | None = None,
    dbname: str | None = None,
    user: str | None = None,
    password: str | None = None,
) -> ApplyResult:
    """Apply migrations from a prebuilt tar.zst artifact (used by wrappers)."""
    artifact = load_artifact(Path(artifact_path))
    config, catalog = _config_and_catalog_from_artifact(artifact)
    return _migrate_with_catalog(
        config,
        catalog,
        pre_post=(artifact.pre_sql(), artifact.post_sql()),
        target=target,
        dry_run=dry_run,
        conninfo=conninfo,
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
    )


def _migrate_with_catalog(
    config: ProjectConfig,
    catalog: Catalog,
    *,
    pre_post: tuple[str, str],
    target: str | None,
    dry_run: bool,
    conninfo: str | None,
    host: str | None,
    port: int | str | None,
    dbname: str | None,
    user: str | None,
    password: str | None,
) -> ApplyResult:
    pre_sql, post_sql = pre_post
    with _conn.connect(
        conninfo,
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
    ) as conn:
        # Need the live version BEFORE planning so we can build the right plan.
        # Use a tiny autocommit-friendly read inside the same connection (pre-txn).
        live_version = _read_live_version_safe(conn, config)
        plan_obj = make_default_plan(catalog, live_version=live_version, target=target)
        return apply_plan(
            conn,
            config,
            catalog,
            plan_obj,
            pre_sql=pre_sql,
            post_sql=post_sql,
            dry_run=dry_run,
        )


def _read_live_version_safe(conn, config: ProjectConfig) -> str | None:  # type: ignore[no-untyped-def]
    """Read current version without breaking the in-progress transaction."""
    # psycopg by default starts a txn on first execute. We rollback after the read
    # so the apply_plan transaction starts clean.
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT to_regclass(%s)",
                (f"{config.tracking_schema}.{config.tracking_table}",),
            )
            exists = cur.fetchone()[0]
            if exists is None:
                conn.rollback()
                return None
            cur.execute(
                sql.SQL("SELECT version FROM {schema}.{table} ORDER BY id DESC LIMIT 1").format(
                    schema=sql.Identifier(config.tracking_schema),
                    table=sql.Identifier(config.tracking_table),
                )
            )
            row = cur.fetchone()
            conn.rollback()
            return row[0] if row else None
    except Exception:
        conn.rollback()
        raise


def verify_round_trip(
    project_root: str | Path,
    *,
    base_url: str = "postgresql:///postgres",
) -> list[str]:
    """For each incremental edge (a, b) where both base files exist, confirm that
    loading <prefix>--a.sql then the incremental gives the same schema as
    loading <prefix>--b.sql directly. Returns a list of human-readable problems
    (empty list = OK)."""
    try:
        from results.tempdb import temporary_local_db
    except ImportError as exc:  # pragma: no cover
        raise PgpkgError(
            "verify_round_trip requires the 'diff' extra (pip install pgpkg[diff])",
            code="E_VERIFY",
        ) from exc

    project = load_project(project_root)
    catalog = project.catalog
    problems: list[str] = []

    for from_v, to_v, edge_path in catalog.edges:
        from_base = catalog.base_files.get(from_v)
        to_base = catalog.base_files.get(to_v)
        if from_base is None or to_base is None:
            continue  # can only verify edges between two staged versions
        from_sql = from_base.read_text(encoding="utf-8")
        to_sql = to_base.read_text(encoding="utf-8")
        inc_sql = edge_path.read_text(encoding="utf-8")

        with (
            temporary_local_db(base_url) as db_inc,
            temporary_local_db(base_url) as db_target,
        ):
            with db_inc.t() as t:
                t.execute(from_sql)
                t.execute(inc_sql)
            with db_target.t() as t:
                t.execute(to_sql)
            diff = db_inc.schemadiff_as_sql(db_target)
        if diff.strip():
            problems.append(
                f"Edge {from_v} -> {to_v} ({edge_path.name}): incremental does not "
                f"converge to base. Diff:\n{diff}"
            )
    return problems


def _config_and_catalog_from_artifact(
    artifact: LoadedArtifact,
) -> tuple[ProjectConfig, Catalog]:
    """Reconstruct a ProjectConfig + Catalog from an in-memory artifact, using a
    temp directory to materialize files so existing parsers work unchanged."""
    import tempfile

    tmp_root = Path(tempfile.mkdtemp(prefix="pgpkg_artifact_"))
    mig_dir = tmp_root / "migrations"
    mig_dir.mkdir()
    # Register cleanup so the temp tree is removed when the process exits.
    atexit.register(shutil.rmtree, tmp_root, True)
    for name, data in artifact.migrations_files().items():
        (mig_dir / Path(name).name).write_bytes(data)

    pre_dir = tmp_root / "sql" / "pre"
    pre_dir.mkdir(parents=True)
    post_dir = tmp_root / "sql" / "post"
    post_dir.mkdir(parents=True)
    for name, data in artifact.files.items():
        if name.startswith("pre/"):
            (pre_dir / Path(name).name).write_bytes(data)
        elif name.startswith("post/"):
            (post_dir / Path(name).name).write_bytes(data)

    config = ProjectConfig(
        project_name=artifact.manifest.project_name,
        prefix=artifact.manifest.prefix,
        sql_dir=tmp_root / "sql",
        migrations_dir=mig_dir,
        pre_dir=pre_dir,
        post_dir=post_dir,
        project_root=tmp_root,
    )
    catalog = build_catalog(config)
    return config, catalog
