# Architecture

A short tour of the modules:

| module | purpose |
|---|---|
| `pgpkg.config` | parse `[tool.pgpkg]` from pyproject.toml into `ProjectConfig` |
| `pgpkg.layout` | parse migration filenames; enumerate `sql/*.sql` fragments |
| `pgpkg.catalog` | turn `migrations/` into a `Catalog` (base files + edges), detect conflicts |
| `pgpkg.staging` | render `sql/` into a single string with fragment markers |
| `pgpkg.versioning` | PEP 440 + `unreleased`-last ordering |
| `pgpkg.planner` | BFS over the catalog graph for shortest `source → target` paths |
| `pgpkg.diff` | wrap `results.temporary_local_db` + `schemadiff_as_sql` |
| `pgpkg.tracking` | `pgpkg.migrations` DDL, advisory locks, sha256 bookkeeping |
| `pgpkg.executor` | run a plan in one xact with `pg_advisory_xact_lock` |
| `pgpkg._conn` | thin psycopg helper honoring libpq env vars |
| `pgpkg.artifact` | build and load the tar.zst artifact (MANIFEST with sha256) |
| `pgpkg.api` | public facade |
| `pgpkg.cli` | argparse CLI, psql-compatible DB flags |
| `pgpkg.wrapper` | scaffold a wrapper Python project |

## Invariants

- The tracking table `pgpkg.migrations` is the source of truth for the
  installed version.
- `sql/` is always "unreleased". Staging it writes an immutable base file.
- Every applied step runs inside one transaction with a project-scoped
  advisory lock (`pg_advisory_xact_lock(sha256(project_name)[:8])`).
- `sql/pre/*` runs before every step; `sql/post/*` runs after. Together
  they form the project's public boundary for side effects (roles, grants,
  GUCs).

## What pgpkg deliberately does *not* do

- No schema adoption (no "adopt an already-installed schema as a version"
  flow). If a DB was seeded out-of-band, you're responsible for inserting
  the right row into `pgpkg.migrations`.
- No downgrades, no per-version `sql/<version>/` tree, no built-in
  pg_tle/control/deb/PGXN packaging.
- No compiled C — `pgpkg` is pure Python.

## Dependencies

| dep | why |
|---|---|
| `psycopg[binary]>=3.1` | the postgres driver |
| `packaging>=23.0` | PEP 440 version comparison |
| `zstandard>=0.22` | tar.zst artifact compression |
| `results>=1.4` (optional `diff` extra) | `temporary_local_db` + `schemadiff_as_sql` |
