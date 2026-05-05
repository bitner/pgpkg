from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import psycopg
import pytest

from pgpkg.config import ProjectConfig
from pgpkg.errors import ConfigError
from pgpkg.tracking import DefaultVersionSource, resolve_version_source


class _DummyVersionSource:
    def read_live_version(self, conn, config):  # type: ignore[no-untyped-def]
        return "1.2.3"

    def record_applied(self, conn, config, *, version, sha256, filename):  # type: ignore[no-untyped-def]
        return None


def _config(*, version_source: str | None = None) -> ProjectConfig:
    return ProjectConfig(
        project_name="sampleext",
        prefix="sampleext",
        sql_dir=Path("sql"),
        migrations_dir=Path("migrations"),
        pre_dir=Path("sql/pre"),
        post_dir=Path("sql/post"),
        project_root=Path("."),
        version_source=version_source,
    )


def test_resolve_version_source_defaults_to_builtin():
    resolved = resolve_version_source(_config())
    assert isinstance(resolved, DefaultVersionSource)


def test_resolve_version_source_uses_override_instance():
    source = _DummyVersionSource()
    resolved = resolve_version_source(_config(), override=source)
    assert resolved is source


def test_resolve_version_source_imports_class(monkeypatch: pytest.MonkeyPatch):
    fake_module = SimpleNamespace(CustomSource=_DummyVersionSource)

    def fake_import_module(name: str):
        assert name == "demo.module"
        return fake_module

    monkeypatch.setattr("pgpkg.tracking.import_module", fake_import_module)
    resolved = resolve_version_source(_config(version_source="demo.module:CustomSource"))
    assert isinstance(resolved, _DummyVersionSource)


def test_resolve_version_source_imports_relative_to_project_root(tmp_path: Path):
    (tmp_path / "custom_source.py").write_text(
        "\n".join(
            [
                "class VersionSource:",
                "    def read_live_version(self, conn, config):",
                "        return '1.2.3'",
                "",
                "    def record_applied(self, conn, config, *, version, sha256, filename):",
                "        return None",
            ]
        )
    )
    config = ProjectConfig(
        project_name="sampleext",
        prefix="sampleext",
        sql_dir=tmp_path / "sql",
        migrations_dir=tmp_path / "migrations",
        pre_dir=tmp_path / "sql" / "pre",
        post_dir=tmp_path / "sql" / "post",
        project_root=tmp_path,
        version_source="custom_source:VersionSource",
    )

    resolved = resolve_version_source(config)

    assert resolved.read_live_version(cast(psycopg.Connection, object()), config) == "1.2.3"


def test_resolve_version_source_rejects_missing_methods(
    monkeypatch: pytest.MonkeyPatch,
):
    fake_module = SimpleNamespace(BadSource=object)

    monkeypatch.setattr("pgpkg.tracking.import_module", lambda name: fake_module)

    with pytest.raises(ConfigError):
        resolve_version_source(_config(version_source="demo.module:BadSource"))
