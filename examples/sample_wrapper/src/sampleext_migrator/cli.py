"""CLI for sampleext: bakes migrations.tar.zst in the wheel."""
from __future__ import annotations

import argparse
import sys
from importlib.resources import files

from pgpkg.api import migrate_from_artifact
from pgpkg.cli import _add_db_args, _resolve_password
from pgpkg.errors import PgpkgError


def _artifact_path():
    return files("sampleext_migrator").joinpath("migrations.tar.zst")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="sampleext-migrator", add_help=False)
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
                print(f"bootstrapped to {res.bootstrapped_from}")
            for f, t in res.applied_steps:
                print(f"applied {f} -> {t}")
            print(f"final version: {res.final_version}")
            return 0
        if args.cmd == "info":
            from pgpkg.artifact import load_artifact

            art = load_artifact(_artifact_path())
            print(f"project: {art.manifest.project_name}")
            print(f"prefix:  {art.manifest.prefix}")
            for e in art.manifest.entries:
                print(f"  {e.name}  {e.sha256[:12]}  {e.size}B")
            return 0
        return 2
    except PgpkgError as exc:
        print(f"error [{exc.code}]: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
