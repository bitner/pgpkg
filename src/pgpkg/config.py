"""Project configuration loaded from pyproject.toml [tool.pgpkg]."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from .errors import ConfigError


@dataclass(frozen=True)
class ProjectConfig:
    """Resolved [tool.pgpkg] project configuration."""

    project_name: str
    prefix: str
    sql_dir: Path
    migrations_dir: Path
    pre_dir: Path
    post_dir: Path
    project_root: Path
    tracking_schema: str = "pgpkg"
    tracking_table: str = "migrations"


def load_config(project_root: str | Path) -> ProjectConfig:
    """Load [tool.pgpkg] from <project_root>/pyproject.toml.

    Required keys: project_name (or fallback to [project].name).
    Optional keys: prefix (default = project_name), sql_dir (default 'sql'),
    migrations_dir (default 'migrations'), tracking.schema, tracking.table.
    """
    root = Path(project_root).resolve()
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        raise ConfigError(f"No pyproject.toml found at {pyproject}")
    with pyproject.open("rb") as fh:
        data = tomllib.load(fh)

    pgpkg_cfg = data.get("tool", {}).get("pgpkg")
    if pgpkg_cfg is None:
        raise ConfigError(
            f'Missing [tool.pgpkg] section in {pyproject}. Add at least project_name = "...".'
        )

    project_name = pgpkg_cfg.get("project_name") or data.get("project", {}).get("name")
    if not project_name:
        raise ConfigError("[tool.pgpkg].project_name is required (or set [project].name).")
    if not isinstance(project_name, str) or not project_name.strip():
        raise ConfigError("[tool.pgpkg].project_name must be a non-empty string.")

    prefix = pgpkg_cfg.get("prefix", project_name)
    if not isinstance(prefix, str) or not prefix:
        raise ConfigError("[tool.pgpkg].prefix must be a non-empty string.")

    sql_dir = root / pgpkg_cfg.get("sql_dir", "sql")
    migrations_dir = root / pgpkg_cfg.get("migrations_dir", "migrations")
    pre_dir = sql_dir / "pre"
    post_dir = sql_dir / "post"

    tracking = pgpkg_cfg.get("tracking", {}) or {}
    tracking_schema = tracking.get("schema", "pgpkg")
    tracking_table = tracking.get("table", "migrations")

    return ProjectConfig(
        project_name=project_name,
        prefix=prefix,
        sql_dir=sql_dir,
        migrations_dir=migrations_dir,
        pre_dir=pre_dir,
        post_dir=post_dir,
        project_root=root,
        tracking_schema=tracking_schema,
        tracking_table=tracking_table,
    )


@dataclass(frozen=True)
class Project:
    """A project = config + its on-disk migrations catalog."""

    config: ProjectConfig
    catalog: Catalog  # forward — defined in catalog.py


# Imported here to avoid circular import at top of file
from .catalog import Catalog, build_catalog  # noqa: E402


def load_project(project_root: str | Path) -> Project:
    """Load config + discover migrations directory."""
    config = load_config(project_root)
    catalog = build_catalog(config)
    return Project(config=config, catalog=catalog)
