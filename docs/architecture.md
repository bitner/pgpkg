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
| `pgpkg.tracking` | default tracking DDL, version-source protocol, role-safe bookkeeping |
| `pgpkg.executor` | run a plan in one xact with `pg_advisory_xact_lock` |
| `pgpkg._conn` | thin psycopg helper honoring libpq env vars |
| `pgpkg.artifact` | build and load the tar.zst artifact (MANIFEST with checksums + runtime config) |
| `pgpkg.api` | public facade |
| `pgpkg.cli` | argparse CLI, psql-compatible DB flags |
| `pgpkg.wrapper` | scaffold a wrapper Python project |

## Invariants

- The installed version comes from the configured version source. By default
  that is `pgpkg.migrations`, but projects can relocate the table or provide a
  custom `module:attribute` implementation.
- `sql/` is always "unreleased". Staging it writes an immutable base file.
- Every applied step runs inside one transaction with a project-scoped
  advisory lock (`pg_advisory_xact_lock(sha256(project_name)[:8])`).
- `sql/pre/*` runs before every step; `sql/post/*` runs after. Together
  they form the project's public boundary for side effects (roles, grants,
  GUCs).
- Tracking writes always run as the original session user, even if migration
  SQL temporarily changes the active role.
- Artifacts preserve runtime tracking defaults so wrapper and bundle-based
  execution see the same config as source-tree execution.

## What pgpkg deliberately does *not* do

- No schema adoption (no "adopt an already-installed schema as a version"
  flow). If a DB was seeded out-of-band, you're responsible for inserting
  the right row into the configured tracking source.
- No downgrades, no per-version `sql/<version>/` tree, no built-in
  pg_tle/control/deb/PGXN packaging.
- No generic wrapper generation for projects with custom version sources.
  Those projects need a project-specific wrapper so they can construct and
  pass the runtime `version_source` object explicitly.
- No compiled C — `pgpkg` is pure Python.

## Dependencies

| dep | why |
|---|---|
| `psycopg[binary]>=3.1` | the postgres driver |
| `packaging>=23.0` | PEP 440 version comparison |
| `zstandard>=0.22` | tar.zst artifact compression |
| `results>=1.4` (optional `diff` extra) | `temporary_local_db` + `schemadiff_as_sql` |
