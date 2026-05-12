from __future__ import annotations

from pathlib import Path

import pytest

from pgpkg._conn import connect
from pgpkg.api import (
    apply_migrations,
    bundle_project,
    migrate,
    migrate_from_artifact,
    verify_round_trip,
)
from pgpkg.tracking import DefaultVersionSource, current_tracking_version

pytestmark = pytest.mark.integration


def _drop_everything(pg_url: str) -> None:
    with connect(pg_url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("DROP SCHEMA IF EXISTS pgpkg CASCADE")
        cur.execute("DROP SCHEMA IF EXISTS sampleext CASCADE")


class ProjectVersionSource:
    def read_live_version(self, conn, config):  # type: ignore[no-untyped-def]
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('sampleext.project_migrations')")
            row = cur.fetchone()
            if row is None or row[0] is None:
                return None
            cur.execute("SELECT version FROM sampleext.project_migrations ORDER BY id DESC LIMIT 1")
            version_row = cur.fetchone()
            return version_row[0] if version_row else None

    def record_applied(self, conn, config, *, version, sha256, filename):  # type: ignore[no-untyped-def]
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS sampleext.project_migrations (
                    id serial PRIMARY KEY,
                    version text NOT NULL,
                    filename text NOT NULL
                )
                """
            )
            cur.execute(
                "INSERT INTO sampleext.project_migrations (version, filename) VALUES (%s, %s)",
                (version, filename),
            )


class ExtendingDefaultVersionSource(DefaultVersionSource):
    def record_applied(self, conn, config, *, version, sha256, filename):  # type: ignore[no-untyped-def]
        super().record_applied(
            conn,
            config,
            version=version,
            sha256=sha256,
            filename=filename,
        )
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS sampleext.project_migrations (
                    id serial PRIMARY KEY,
                    version text NOT NULL,
                    filename text NOT NULL
                )
                """
            )
            cur.execute(
                "INSERT INTO sampleext.project_migrations (version, filename) VALUES (%s, %s)",
                (version, filename),
            )


class ValidatingProjectVersionSource:
    def read_live_version(self, conn, config):  # type: ignore[no-untyped-def]
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('sampleext.project_migrations')")
            row = cur.fetchone()
            if row is None or row[0] is None:
                return None
            cur.execute("SELECT version FROM sampleext.project_migrations ORDER BY id DESC LIMIT 1")
            version_row = cur.fetchone()
            return version_row[0] if version_row else None

    def record_applied(self, conn, config, *, version, sha256, filename):  # type: ignore[no-untyped-def]
        tracking_version = current_tracking_version(
            conn,
            schema=config.tracking_schema,
            table=config.tracking_table,
        )
        if tracking_version != version:
            raise RuntimeError(
                f"tracking version mismatch: expected {version!r}, got {tracking_version!r}"
            )

        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS sampleext.project_migrations (
                    id serial PRIMARY KEY,
                    version text NOT NULL,
                    filename text NOT NULL
                )
                """
            )
            cur.execute(
                "INSERT INTO sampleext.project_migrations (version, filename) VALUES (%s, %s)",
                (version, filename),
            )


def _configure_role_switch_sql(project_root: Path) -> None:
    pre_dir = project_root / "sql" / "pre"
    post_dir = project_root / "sql" / "post"
    pre_dir.mkdir(parents=True, exist_ok=True)
    post_dir.mkdir(parents=True, exist_ok=True)

    (pre_dir / "001_runtime_role.sql").write_text(
        """
        DO $$
        BEGIN
            CREATE ROLE sample_runtime_role;
        EXCEPTION WHEN duplicate_object THEN
            NULL;
        END
        $$;
        GRANT sample_runtime_role TO CURRENT_USER;
        """
    )
    (post_dir / "999_runtime_role.sql").write_text("SET ROLE sample_runtime_role;\n")


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


def test_custom_version_source_reads_and_records_project_version(
    staged_project: Path,
    pg_url: str,
):
    _drop_everything(pg_url)
    source = ProjectVersionSource()

    first = apply_migrations(
        staged_project,
        target="0.1.0",
        conninfo=pg_url,
        version_source=source,
    )
    assert first.applied == ["0.1.0"]

    with connect(pg_url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT version FROM pgpkg.migrations ORDER BY id")
        assert [r[0] for r in cur.fetchall()] == ["0.1.0"]
        cur.execute("SELECT version FROM sampleext.project_migrations ORDER BY id")
        assert [r[0] for r in cur.fetchall()] == ["0.1.0"]

    second = apply_migrations(
        staged_project,
        target="0.2.0",
        conninfo=pg_url,
        version_source=source,
    )
    assert second.applied == ["0.2.0"]

    with connect(pg_url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT version FROM pgpkg.migrations ORDER BY id")
        assert [r[0] for r in cur.fetchall()] == ["0.1.0", "0.2.0"]
        cur.execute("SELECT version FROM sampleext.project_migrations ORDER BY id")
        assert [r[0] for r in cur.fetchall()] == ["0.1.0", "0.2.0"]


def test_default_version_source_subclass_does_not_duplicate_tracking_rows(
    staged_project: Path,
    pg_url: str,
):
    _drop_everything(pg_url)
    source = ExtendingDefaultVersionSource()

    result = apply_migrations(
        staged_project,
        target="0.2.0",
        conninfo=pg_url,
        version_source=source,
    )
    assert "0.2.0" in result.applied

    with connect(pg_url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT version FROM pgpkg.migrations ORDER BY id")
        assert [r[0] for r in cur.fetchall()] == ["0.2.0"]
        cur.execute("SELECT version FROM sampleext.project_migrations ORDER BY id")
        assert [r[0] for r in cur.fetchall()] == ["0.2.0"]


def test_migrate_from_artifact_uses_override_version_source(
    staged_project: Path,
    pg_url: str,
    tmp_path: Path,
):
    _drop_everything(pg_url)
    (staged_project / "pyproject.toml").write_text(
        "\n".join(
            [
                "[tool.pgpkg]",
                'project_name = "sampleext"',
                'prefix = "sampleext"',
                'version_source = "does.not.exist:VersionSource"',
            ]
        )
    )
    artifact = tmp_path / "sampleext.tar.zst"
    bundle_project(staged_project, artifact)

    result = migrate_from_artifact(
        artifact,
        target="0.2.0",
        conninfo=pg_url,
        version_source=ProjectVersionSource(),
    )

    assert result.applied == ["0.2.0"]

    with connect(pg_url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT version FROM pgpkg.migrations ORDER BY id")
        assert [r[0] for r in cur.fetchall()] == ["0.2.0"]
        cur.execute("SELECT version FROM sampleext.project_migrations ORDER BY id")
        assert [r[0] for r in cur.fetchall()] == ["0.2.0"]


def test_default_tracking_survives_set_role_in_migration_sql(
    staged_project: Path,
    pg_url: str,
):
    _drop_everything(pg_url)
    _configure_role_switch_sql(staged_project)

    result = apply_migrations(staged_project, target="0.2.0", conninfo=pg_url)

    assert result.applied == ["0.2.0"]

    with connect(pg_url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT version FROM pgpkg.migrations ORDER BY id")
        assert [r[0] for r in cur.fetchall()] == ["0.2.0"]


def test_custom_version_source_can_validate_tracking_after_set_role(
    staged_project: Path,
    pg_url: str,
):
    _drop_everything(pg_url)
    _configure_role_switch_sql(staged_project)

    result = apply_migrations(
        staged_project,
        target="0.2.0",
        conninfo=pg_url,
        version_source=ValidatingProjectVersionSource(),
    )

    assert result.applied == ["0.2.0"]

    with connect(pg_url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT version FROM pgpkg.migrations ORDER BY id")
        assert [r[0] for r in cur.fetchall()] == ["0.2.0"]
        cur.execute("SELECT version FROM sampleext.project_migrations ORDER BY id")
        assert [r[0] for r in cur.fetchall()] == ["0.2.0"]
