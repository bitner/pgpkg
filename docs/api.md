# Python API

Everything the CLI does is available as a Python API. Import from `pgpkg`:

```python
from pgpkg import (
    list_versions,
    stage_version,
    generate_incremental,
    plan_path,
    apply_migrations,
    migrate,
    verify_round_trip,
)
```

## `list_versions(project_root) -> list[str]`

All known versions (released + unreleased), sorted. `unreleased` always
last.

## `stage_version(project_root, version, *, output_path=None, overwrite=True) -> Path`

Render `sql/` into `<prefix>--<version>.sql`. Returns the path written.

## `generate_incremental(project_root, *, from_version, to_version, base_url, output_path=None) -> Path`

Diff two staged base files through `results.temporary_local_db` and write
`<prefix>--<from>--<to>.sql`.

## `plan_path(project_root, *, source, target) -> MigrationPlan`

Return the shortest chain of incrementals from `source` to `target`. If
`source is None`, the plan starts with a bootstrap base file.

## `apply_migrations(project_root, *, target=None, dry_run=False, conninfo=None, host=None, port=None, dbname=None, user=None, password=None) -> ApplyResult`

Apply the plan to a live database. Accepts psycopg-style kwargs; all
default to libpq env vars (`PGHOST`, `PGPORT`, …).

`migrate` is an alias for `apply_migrations`.

### `ApplyResult`

```python
@dataclass
class ApplyResult:
    bootstrapped_from: str | None
    applied_steps: list[tuple[str, str]]
    final_version: str | None

    @property
    def applied(self) -> list[str]: ...
```

## `verify_round_trip(project_root, *, base_url) -> list[str]`

For each incremental `(a, b)` where both have staged base files, confirm
that `base(a) + a→b` produces the same schema as `base(b)`. Returns a list
of problems (empty = OK).

## `build_artifact(config, output_path) -> Path`

Bundle `migrations/` + `sql/pre/` + `sql/post/` into a reproducible
`tar.zst` with a `MANIFEST.json` containing SHA-256 per entry.

## `migrate_from_artifact(artifact_path, *, target=None, ...) -> ApplyResult`

Like `migrate`, but reads every migration + pre/post from a baked
`tar.zst`. Used by wrapper wheels.
