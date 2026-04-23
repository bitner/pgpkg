# Quickstart

Start from any project that has a `pyproject.toml`.

## 1. Declare your project

```toml
# pyproject.toml
[tool.pgpkg]
project_name = "myext"
# prefix defaults to project_name; override if you need a different file prefix
# prefix = "myext"
```

## 2. Write your schema

Create `sql/` and write files in the order they should load:

```
sql/
  010_schema.sql
  020_tables.sql
  030_functions.sql
  pre/
    001_roles.sql          # runs BEFORE every migration (bootstrap or step)
  post/
    999_grants.sql         # runs AFTER every migration
```

`sql/` always represents the **current, unreleased** state of the database.

## 3. Stage a version

```
pgpkg stageversion 0.1.0
```

This writes `migrations/myext--0.1.0.sql`. Never edit that file by hand.

## 4. Keep editing `sql/`, then generate an incremental

```
pgpkg stageversion 0.2.0
pgpkg makemigration --from 0.1.0 --to 0.2.0
```

This spins up two temporary postgres databases (via `results.temporary_local_db`),
loads the two staged base files into them, and writes the diff to
`migrations/myext--0.1.0--0.2.0.sql`.

Review the diff. Edit freely; `pgpkg verify` will round-trip-check it later.

## 5. Apply to a live DB

```
pgpkg migrate -h localhost -d mydb -U myuser --to 0.2.0
```

Standard libpq environment variables (`PGHOST`, `PGPORT`, `PGDATABASE`,
`PGUSER`, `PGPASSWORD`) are honored. You can also pass `--dsn 'postgresql://...'`.

## 6. Verify

```
pgpkg verify
```

For every incremental `(a -> b)` where `a` and `b` both have staged base files,
this checks that loading `base(a) + a→b` produces the same schema as
loading `base(b)` directly.

## 7. Ship

```
pgpkg wheel --output-dir ../myext-migrator
cd ../myext-migrator && uv build
```

The resulting wheel ships a `<project>-migrator migrate` console script that
bakes every staged artifact and does not need the source tree at runtime.
See [Wrapping into a wheel](wrapper.md).
