# CLI reference

`pgpkg` uses argparse and accepts `--help` (the `-h` short flag is reserved
for `--host`, matching `psql`).

```text
pgpkg [--help] <command> [options]

Commands:
  info            Show resolved project info
  versions        List known versions in order
  stageversion    Render <prefix>--<version>.sql from sql/
  makemigration   Generate <prefix>--<from>--<to>.sql by diffing two staged base files
  graph           Show the version graph
  plan            Show migration plan from --source to --to
  migrate         Apply migrations to a live database
  verify          Round-trip every (a -> b) edge and confirm convergence
  wheel           Scaffold a wrapper Python project that bakes migrations/ into a wheel
  bundle          Bundle migrations/ + sql/pre + sql/post into a tar.zst
```

## Shared flags

- `--project-root <path>` — defaults to `$PGPKG_PROJECT_ROOT` or `.`.

## DB flags (psql-compatible)

`migrate` accepts the same environment variables as `libpq`/`psql`:

| short | long | env | purpose |
|---|---|---|---|
| `-h` | `--host` | `PGHOST` | host |
| `-p` | `--port` | `PGPORT` | port |
| `-d` | `--dbname` | `PGDATABASE` | database |
| `-U` | `--user` | `PGUSER` | user |
| `-W` | `--password-prompt` | — | prompt for password |
|  | `--dsn` | | full `postgresql://...` string, overrides the other flags |

If `--dsn` is empty and the individual flags are not passed, libpq env
vars take over.

## `stageversion`

```text
pgpkg stageversion <version> [--output PATH] [--also-write PATH] [--no-overwrite]
```

Renders `sql/` into a single `<prefix>--<version>.sql`. Ignores `sql/pre/`
and `sql/post/` (they run at apply time).

- `--output` overrides the default path under `migrations/`.
- `--also-write` writes the same rendered base file to a second location,
  which is useful for review artifacts or custom packaging flows.
- `--no-overwrite` preflights every destination and fails before writing if
  any target already exists.

## `info`

```
pgpkg info [--json]
```

Prints resolved project metadata including the inferred prefix, SQL and
migrations directories, tracking schema/table, configured `version_source`,
known versions, base files, and graph edges.

## `versions`

```
pgpkg versions
```

Prints known versions in sorted order, including `unreleased` when present.

## `makemigration`

```text
pgpkg makemigration [--from VERSION] [--to VERSION] [--base-url URL] [--output PATH]
                   [--prepend-file PATH]... [--append-file PATH]...
                   [--append-sql SQL]...
```

Writes `<prefix>--<from>--<to>.sql`. `--base-url` is the postgres URL used
to spawn tempdbs via `results.temporary_local_db`. Defaults to
`postgresql:///postgres`, i.e. a local admin connection through the peer
socket.

When wrapper SQL is supplied, `pgpkg` renders the output in this order:

1. Every `--prepend-file`.
2. The generated schema diff.
3. Every `--append-file`.
4. Every `--append-sql` literal.

## `graph`

```text
pgpkg graph [--format text|dot]
```

Shows the version graph either as plain text or Graphviz DOT.

## `plan`

```text
pgpkg plan [--source VERSION] [--to VERSION]
```

Shows the shortest migration plan. If `--source` is omitted, the plan assumes
a fresh install and may start with a bootstrap base file.

## `migrate`

```text
pgpkg migrate [--to VERSION] [--dry-run] <db-flags>
```

Runs inside one transaction with `pg_advisory_xact_lock`. `--dry-run`
executes the same SQL inside a transaction, then rolls back. The live source
version comes from the configured version source, which defaults to
`pgpkg.migrations`.

## `verify`

```text
pgpkg verify [--base-url URL]
```

Round-trips every incremental edge through temporary databases and confirms
that applying `a -> b` produces the same resulting schema as loading base `b`.

## `wheel`

```text
pgpkg wheel --output-dir PATH [--cli-name NAME]
```

Scaffolds a wrapper Python project. Projects using
`[tool.pgpkg].version_source` must ship a custom wrapper instead; the generic
scaffold rejects that configuration so the wrapper can pass an explicit
`version_source=...` object at runtime. See [Wrapping into a wheel](wrapper.md).

## `bundle`

```text
pgpkg bundle --output PATH
```

Writes a compressed `tar.zst` artifact containing `migrations/`, `sql/pre/`,
and `sql/post/`. The manifest also records the resolved tracking schema,
tracking table, and configured `version_source` string so artifact-based
execution keeps the same runtime defaults. This is useful for automation or
for shipping migration artifacts separately from a full wrapper project.
