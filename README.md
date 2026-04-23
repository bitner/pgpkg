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

## Quickstart

```bash
pip install 'pgpkg[diff]'

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

See [docs/](docs/) for the full manual, or [PROJECT_PLAN.md](PROJECT_PLAN.md)
for the design document.

## License

MIT
