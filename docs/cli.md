# CLI reference

`pgpkg` uses argparse and accepts `--help` (the `-h` short flag is reserved
for `--host`, matching `psql`).

```
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

```
pgpkg stageversion <version> [--output PATH] [--no-overwrite]
```

Renders `sql/` into a single `<prefix>--<version>.sql`. Ignores `sql/pre/`
and `sql/post/` (they run at apply time).

## `makemigration`

```
pgpkg makemigration [--from VERSION] [--to VERSION] [--base-url URL] [--output PATH]
```

Writes `<prefix>--<from>--<to>.sql`. `--base-url` is the postgres URL used
to spawn tempdbs via `results.temporary_local_db`. Defaults to
`postgresql:///postgres`, i.e. a local admin connection through the peer
socket.

## `migrate`

```
pgpkg migrate [--to VERSION] [--dry-run] <db-flags>
```

Runs inside one transaction with `pg_advisory_xact_lock`. `--dry-run`
executes the same SQL inside a transaction, then rolls back.

## `wheel`

```
pgpkg wheel --output-dir PATH [--cli-name NAME]
```

Scaffolds a wrapper Python project. See [Wrapping into a wheel](wrapper.md).
