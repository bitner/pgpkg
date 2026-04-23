"""Command-line interface (argparse, no external deps)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import api
from .errors import PgpkgError
from .versioning import UNRELEASED


def _add_db_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--dsn", help="libpq conninfo string (overrides individual flags)")
    p.add_argument("-h", "--host", help="DB host (PGHOST)", default=None)
    p.add_argument("-p", "--port", help="DB port (PGPORT)", default=None)
    p.add_argument("-d", "--dbname", help="DB name (PGDATABASE)", default=None)
    p.add_argument("-U", "--user", help="DB user (PGUSER)", default=None)
    # password: take from PGPASSWORD or interactive prompt; -W requests prompt
    p.add_argument(
        "-W",
        "--password-prompt",
        action="store_true",
        help="Prompt for password (otherwise PGPASSWORD or libpq fallback is used)",
    )


def _resolve_password(args: argparse.Namespace) -> str | None:
    if getattr(args, "password_prompt", False):
        import getpass

        return getpass.getpass("Password: ")
    return None  # let libpq env (PGPASSWORD) take over


def _project_root_arg(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--project-root",
        default=os.environ.get("PGPKG_PROJECT_ROOT", "."),
        help="Path to project root (containing pyproject.toml). Default: current dir.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pgpkg",
        description="PostgreSQL migration toolkit",
        # disable -h shortcut so we can use it for --host like psql
        add_help=False,
    )
    parser.add_argument("--help", action="help", help="Show help and exit")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # info
    p_info = sub.add_parser("info", help="Show resolved project info")
    _project_root_arg(p_info)
    p_info.add_argument("--json", action="store_true")

    # versions
    p_versions = sub.add_parser("versions", help="List known versions in order")
    _project_root_arg(p_versions)

    # stageversion
    p_stage = sub.add_parser(
        "stageversion",
        help="Render <prefix>--<version>.sql from sql/",
    )
    _project_root_arg(p_stage)
    p_stage.add_argument("version", help="Version to stage (PEP 440 or 'unreleased')")
    p_stage.add_argument("--output", type=Path, help="Override output path")
    p_stage.add_argument(
        "--no-overwrite",
        action="store_true",
        help="Fail if the target file already exists",
    )

    # makemigration
    p_make = sub.add_parser(
        "makemigration",
        help="Generate <prefix>--<from>--<to>.sql by diffing two staged base files",
    )
    _project_root_arg(p_make)
    p_make.add_argument(
        "--from", dest="from_version", help="Source version (default: highest released)"
    )
    p_make.add_argument("--to", dest="to_version", help=f"Target version (default: '{UNRELEASED}')")
    p_make.add_argument("--output", type=Path, help="Override output path")
    p_make.add_argument(
        "--base-url",
        default="postgresql:///postgres",
        help="postgres URL used by `results.temporary_local_db` to spin up tempdbs",
    )

    # graph
    p_graph = sub.add_parser("graph", help="Show the version graph")
    _project_root_arg(p_graph)
    p_graph.add_argument("--format", choices=["text", "dot"], default="text")

    # plan
    p_plan = sub.add_parser("plan", help="Show migration plan from --source to --to")
    _project_root_arg(p_plan)
    p_plan.add_argument("--source", help="Source version (omit for fresh-install plan)")
    p_plan.add_argument("--to", dest="target", help="Target version (default: highest)")

    # migrate
    p_mig = sub.add_parser(
        "migrate",
        help="Apply migrations to a live database",
        add_help=False,
    )
    p_mig.add_argument("--help", action="help", help="Show help and exit")
    _project_root_arg(p_mig)
    _add_db_args(p_mig)
    p_mig.add_argument("--to", dest="target", help="Target version (default: highest)")
    p_mig.add_argument("--dry-run", action="store_true", help="Run inside a rolled-back txn")

    # verify
    p_ver = sub.add_parser(
        "verify",
        help="Round-trip every (a -> b) edge through tempdbs and confirm convergence",
    )
    _project_root_arg(p_ver)
    p_ver.add_argument("--base-url", default="postgresql:///postgres")

    # wheel (scaffold a wrapper project)
    p_wheel = sub.add_parser(
        "wheel",
        help="Scaffold a wrapper Python project that bakes migrations/ into a wheel",
    )
    _project_root_arg(p_wheel)
    p_wheel.add_argument(
        "--output-dir", type=Path, required=True, help="Where to write the wrapper project"
    )
    p_wheel.add_argument(
        "--cli-name",
        help="Console script name (default: <project>-migrator)",
    )

    # bundle (raw artifact, useful for scripting)
    p_bundle = sub.add_parser(
        "bundle",
        help="Bundle migrations/ + sql/pre + sql/post into a tar.zst",
    )
    _project_root_arg(p_bundle)
    p_bundle.add_argument("--output", type=Path, required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return _dispatch(args)
    except PgpkgError as exc:
        print(f"error [{exc.code}]: {exc}", file=sys.stderr)
        return 2


def _dispatch(args: argparse.Namespace) -> int:
    cmd = args.cmd
    if cmd == "info":
        return _cmd_info(args)
    if cmd == "versions":
        return _cmd_versions(args)
    if cmd == "stageversion":
        return _cmd_stageversion(args)
    if cmd == "makemigration":
        return _cmd_makemigration(args)
    if cmd == "graph":
        return _cmd_graph(args)
    if cmd == "plan":
        return _cmd_plan(args)
    if cmd == "migrate":
        return _cmd_migrate(args)
    if cmd == "verify":
        return _cmd_verify(args)
    if cmd == "wheel":
        return _cmd_wheel(args)
    if cmd == "bundle":
        return _cmd_bundle(args)
    raise PgpkgError(f"Unknown command: {cmd}")


def _cmd_info(args: argparse.Namespace) -> int:
    project = api.load_project(args.project_root)
    info = {
        "project_name": project.config.project_name,
        "prefix": project.config.prefix,
        "sql_dir": str(project.config.sql_dir),
        "migrations_dir": str(project.config.migrations_dir),
        "versions": project.catalog.versions,
        "base_files": {v: str(p) for v, p in project.catalog.base_files.items()},
        "edges": [{"from": f, "to": t, "file": str(p)} for f, t, p in project.catalog.edges],
    }
    if args.json:
        print(json.dumps(info, indent=2))
    else:
        for k, v in info.items():
            print(f"{k}: {v}")
    return 0


def _cmd_versions(args: argparse.Namespace) -> int:
    for v in api.list_versions(args.project_root):
        print(v)
    return 0


def _cmd_stageversion(args: argparse.Namespace) -> int:
    path = api.stage_version(
        args.project_root,
        args.version,
        output_path=args.output,
        overwrite=not args.no_overwrite,
    )
    print(f"wrote {path}")
    return 0


def _cmd_makemigration(args: argparse.Namespace) -> int:
    project = api.load_project(args.project_root)
    catalog = project.catalog
    from_v = args.from_version or _highest_released(catalog.versions)
    to_v = args.to_version or UNRELEASED
    if from_v is None:
        raise PgpkgError(
            "No --from given and no released versions found in the catalog.",
            code="E_DIFF",
        )
    if from_v == to_v:
        raise PgpkgError(f"--from and --to are the same: {from_v!r}", code="E_DIFF")
    path = api.generate_incremental(
        args.project_root,
        from_version=from_v,
        to_version=to_v,
        base_url=args.base_url,
        output_path=args.output,
    )
    print(f"wrote {path}")
    return 0


def _cmd_graph(args: argparse.Namespace) -> int:
    print(api.render_graph(args.project_root, format=args.format), end="")
    return 0


def _cmd_plan(args: argparse.Namespace) -> int:
    project = api.load_project(args.project_root)
    target = args.target
    if target is None:
        from .versioning import default_target

        target = default_target(project.catalog.versions)
        if target is None:
            raise PgpkgError("Catalog is empty; nothing to plan.", code="E_PLAN")
    p = api.plan_path(args.project_root, source=args.source, target=target)
    print(f"target:    {p.target}")
    print(f"source:    {p.source}")
    print(f"bootstrap: {p.bootstrap_base.name if p.bootstrap_base else '(none)'}")
    print("steps:")
    if not p.steps:
        print("  (none)")
    for s in p.steps:
        print(f"  {s.from_version} -> {s.to_version}  [{s.file.name}]")
    return 0


def _cmd_migrate(args: argparse.Namespace) -> int:
    password = _resolve_password(args)
    res = api.apply_migrations(
        args.project_root,
        target=args.target,
        dry_run=args.dry_run,
        conninfo=args.dsn,
        host=args.host,
        port=args.port,
        dbname=args.dbname,
        user=args.user,
        password=password,
    )
    if res.bootstrapped_from is not None:
        print(f"bootstrapped to {res.bootstrapped_from}")
    for from_v, to_v in res.applied_steps:
        print(f"applied {from_v} -> {to_v}")
    print(f"final version: {res.final_version}")
    if args.dry_run:
        print("(dry-run: rolled back)")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    problems = api.verify_round_trip(args.project_root, base_url=args.base_url)
    if not problems:
        print("OK: all edges converge")
        return 0
    for p in problems:
        print(p)
    return 3


def _cmd_wheel(args: argparse.Namespace) -> int:
    from .wrapper import scaffold_wrapper

    project = api.load_project(args.project_root)
    cli_name = args.cli_name or f"{project.config.project_name}-migrator"
    out = scaffold_wrapper(
        args.project_root,
        output_dir=args.output_dir,
        cli_name=cli_name,
    )
    print(f"wrote wrapper project at {out}")
    return 0


def _cmd_bundle(args: argparse.Namespace) -> int:
    project = api.load_project(args.project_root)
    path = api.build_artifact(project.config, args.output)
    print(f"wrote {path}")
    return 0


def _highest_released(versions: list[str]) -> str | None:
    from .versioning import highest_released

    return highest_released(versions)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
