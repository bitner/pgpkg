# pgpkg

A small, focused PostgreSQL migration toolkit.

You write SQL describing the **exact desired state** of your database in an
ordered `sql/` directory. `pgpkg` does everything else:

1. **`stageversion`** — concatenates `sql/` into a versioned base file
   `<prefix>--<version>.sql`.
2. **`makemigration`** — diffs two staged versions with
   [results](https://github.com/djrobstep/results) to generate an incremental
   migration `<prefix>--A--B.sql`.
3. **`graph`** — shows the version graph and shortest paths between versions.
4. **`migrate`** — connects to a live database (libpq env vars or psql-style
   flags), reads the currently installed version, and applies the shortest
   sequence of incrementals (or bootstraps from a base file) to reach the
   target version.
5. **`wheel`** — scaffolds a self-contained wrapper Python project that bakes
   your migrations into a wheel and exposes a `<project>-migrator` console
   script.
6. **`verify`** — round-trips every edge `(a -> b)` through two throwaway
   databases to prove the incremental produces the same schema as loading
   `<prefix>--b.sql`.
7. **`bundle`** — writes a compressed `tar.zst` artifact containing
   `migrations/` plus `sql/pre/` and `sql/post/` for automation or custom
   packaging flows.

## Prerequisites

- **Python ≥ 3.11** and **uv**
- **`pgpkg[diff]`** — the `makemigration` command requires the optional
  [results](https://github.com/djrobstep/results) dependency:
   `uv tool install --with 'pgpkg[diff]' pgpkg`
- **Docker** — `makemigration` and `verify` spin up throwaway PostgreSQL
  containers via `testcontainers`; Docker must be running
- **libpq** — `migrate` connects to a live database using standard libpq
  environment variables (`PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`,
  `PGPASSWORD`) or explicit `-h/-p/-d/-U/--dsn` flags

## Quickstart

```bash
uv tool install --with 'pgpkg[diff]' pgpkg

mkdir -p sql/pre sql/post
echo "CREATE TABLE foo (id int PRIMARY KEY);" > sql/010_schema.sql

# declare your project once
cat >> pyproject.toml <<'TOML'
[tool.pgpkg]
project_name = "myext"
TOML

# stage a version
pgpkg stageversion 0.1.0

# iterate sql/ and generate an incremental
pgpkg stageversion 0.2.0
pgpkg makemigration --from 0.1.0 --to 0.2.0

# apply to a live database (libpq env vars honored)
pgpkg migrate -d mydb -h localhost --to 0.2.0
```

## Tracking and packaging

By default, `pgpkg` records applied versions in `pgpkg.migrations`. You can
relocate that table with:

```toml
[tool.pgpkg]
project_name = "myext"

[tool.pgpkg.tracking]
schema = "ops"
table = "schema_versions"
```

If your application already owns the authoritative version table, set
`[tool.pgpkg].version_source = "module:attribute"` and provide an object with
`read_live_version(...)` and `record_applied(...)` methods. The generic
`pgpkg wheel` scaffold is intentionally limited to the default tracking path;
custom version sources should use a project-specific wrapper that calls
`pgpkg.api.migrate_from_artifact(..., version_source=...)`.

See the full manual at https://bitner.github.io/pgpkg/ and the source docs in [docs/](docs/).

## Development

```bash
uv sync --extra dev --extra diff
uv run pre-commit install
uv run pre-commit run --all-files
uv run ty check src tests
uv run pytest -q
uv build --out-dir dist
uv run mkdocs build --strict
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the release workflow and trusted-publishing setup.
For initial repository and publishing bootstrap, use your local project bootstrap checklist.

## License

MIT
