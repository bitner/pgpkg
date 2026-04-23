"""Wrapper scaffold: emit a Python project that bakes migrations/ into a wheel.

The emitted wheel:
  - depends on `pgpkg`
  - ships a `<project>-migrator` console script
  - contains `migrations.tar.zst` inside the package as package data
  - on `migrate` subcommand, loads the artifact and calls
    `pgpkg.api.migrate_from_artifact(...)`.
"""

from __future__ import annotations

from pathlib import Path

from .api import build_artifact
from .config import load_project

_PYPROJECT_TMPL = """\
[project]
name = "{dist_name}"
version = "{version}"
description = "Migration wrapper for {project_name}"
requires-python = ">=3.11"
dependencies = [
    "pgpkg>=0.1",
]

[project.scripts]
{cli_name} = "{pkg_name}.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/{pkg_name}"]
"""

_CLI_TMPL = '''\
"""CLI for {project_name}: bakes migrations.tar.zst in the wheel."""
from __future__ import annotations

import argparse
import sys
from importlib.resources import files

from pgpkg.api import migrate_from_artifact
from pgpkg.cli import _add_db_args, _resolve_password
from pgpkg.errors import PgpkgError


def _artifact_path():
    return files("{pkg_name}").joinpath("migrations.tar.zst")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="{cli_name}", add_help=False)
    parser.add_argument("--help", action="help")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_mig = sub.add_parser("migrate", help="Apply baked migrations to a live DB", add_help=False)
    p_mig.add_argument("--help", action="help")
    _add_db_args(p_mig)
    p_mig.add_argument("--to", dest="target", help="Target version (default: highest)")
    p_mig.add_argument("--dry-run", action="store_true")

    sub.add_parser("info", help="Print baked artifact info")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "migrate":
            password = _resolve_password(args)
            res = migrate_from_artifact(
                str(_artifact_path()),
                target=args.target,
                dry_run=args.dry_run,
                conninfo=args.dsn,
                host=args.host,
                port=args.port,
                dbname=args.dbname,
                user=args.user,
                password=password,
            )
            if res.bootstrapped_from:
                print(f"bootstrapped to {{res.bootstrapped_from}}")
            for f, t in res.applied_steps:
                print(f"applied {{f}} -> {{t}}")
            print(f"final version: {{res.final_version}}")
            return 0
        if args.cmd == "info":
            from pgpkg.artifact import load_artifact

            art = load_artifact(_artifact_path())
            print(f"project: {{art.manifest.project_name}}")
            print(f"prefix:  {{art.manifest.prefix}}")
            for e in art.manifest.entries:
                print(f"  {{e.name}}  {{e.sha256[:12]}}  {{e.size}}B")
            return 0
        return 2
    except PgpkgError as exc:
        print(f"error [{{exc.code}}]: {{exc}}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
'''

_INIT_TMPL = '''\
"""{project_name} migrator wrapper."""
__version__ = "{version}"
'''


def scaffold_wrapper(
    project_root: str | Path,
    *,
    output_dir: Path,
    cli_name: str,
    dist_name: str | None = None,
    version: str = "0.0.1",
) -> Path:
    """Emit a wrapper Python project at `output_dir` that bakes the project's
    `migrations/` (+ sql/pre, sql/post) as a `migrations.tar.zst` inside the wheel.

    Returns the output_dir path.
    """
    project = load_project(project_root)
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    pkg_name = (dist_name or f"{project.config.project_name}_migrator").replace("-", "_")
    dist_name_final = dist_name or f"{project.config.project_name}-migrator"

    # 1. pyproject.toml
    (output_dir / "pyproject.toml").write_text(
        _PYPROJECT_TMPL.format(
            dist_name=dist_name_final,
            version=version,
            project_name=project.config.project_name,
            pkg_name=pkg_name,
            cli_name=cli_name,
        ),
        encoding="utf-8",
    )

    # 2. src/<pkg>/__init__.py and cli.py
    pkg_dir = output_dir / "src" / pkg_name
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "__init__.py").write_text(
        _INIT_TMPL.format(project_name=project.config.project_name, version=version),
        encoding="utf-8",
    )
    (pkg_dir / "cli.py").write_text(
        _CLI_TMPL.format(
            pkg_name=pkg_name,
            cli_name=cli_name,
            project_name=project.config.project_name,
        ),
        encoding="utf-8",
    )
    # marker package data file (the real artifact is emitted next to pyproject.toml
    # and force-included into the wheel).
    (pkg_dir / "py.typed").write_text("", encoding="utf-8")

    # 3. Build the tar.zst artifact inside the package directory so it becomes
    # package data that ships in the wheel and is accessible via importlib.resources
    # even in an editable install.
    build_artifact(project.config, pkg_dir / "migrations.tar.zst")

    # 4. A tiny README so users know what to do.
    (output_dir / "README.md").write_text(
        f"# {dist_name_final}\n\n"
        f"Wrapper for `{project.config.project_name}` migrations.\n\n"
        f"Build: `uv build`\n"
        f"Run:   `uv run {cli_name} migrate -d mydb -h localhost`\n",
        encoding="utf-8",
    )

    return output_dir
