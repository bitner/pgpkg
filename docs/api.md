# Python API

The root package exposes the high-level project API:

```python
from pgpkg import (
    apply_migrations,
    bundle_project,
    generate_incremental,
    list_versions,
    load_project,
    migrate,
    plan_path,
    stage_version,
    verify_round_trip,
)

from pgpkg.api import migrate_from_artifact
```

`migrate_from_artifact()` stays in `pgpkg.api` because it is mainly intended
for wrapper packages and automation flows.

## `list_versions(project_root) -> list[str]`

All known versions (released + unreleased), sorted. `unreleased` always
last.

## `stage_version(project_root, version, *, output_path=None, also_write=None, overwrite=True) -> Path`

Render `sql/` into `<prefix>--<version>.sql`. Returns the path written.

If `also_write` is set, the same rendered base file is written to that second
path after all destinations are validated.

## `generate_incremental(project_root, *, from_version, to_version, base_url, output_path=None, prepend_files=None, append_files=None, append_sql=None) -> Path`

Diff two staged base files through `results.temporary_local_db` and write
`<prefix>--<from>--<to>.sql`.

Optional wrapper content is rendered around the generated diff in this order:
`prepend_files`, diff body, `append_files`, then literal `append_sql` strings.

## `plan_path(project_root, *, source, target) -> MigrationPlan`

Return the shortest chain of incrementals from `source` to `target`. If
`source is None`, the plan starts with a bootstrap base file.

## `bundle_project(project_root, output_path) -> Path`

Build a reproducible `tar.zst` artifact from the project root. The manifest
includes migration entry checksums plus the resolved tracking schema, tracking
table, and configured `version_source` string.

## `apply_migrations(project_root, *, target=None, dry_run=False, conninfo=None, host=None, port=None, dbname=None, user=None, password=None, version_source=None) -> ApplyResult`

Apply the plan to a live database. Accepts psycopg-style kwargs; all
default to libpq env vars (`PGHOST`, `PGPORT`, …).

`migrate` is an alias for `apply_migrations`.

If `version_source` is passed, it overrides `[tool.pgpkg].version_source` for
that call only.

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

## `migrate_from_artifact(artifact_path, *, target=None, dry_run=False, conninfo=None, host=None, port=None, dbname=None, user=None, password=None, version_source=None) -> ApplyResult`

Apply migrations from a prebuilt `tar.zst` artifact. This is the runtime entry
point used by wrapper wheels.

If the artifact manifest contains tracking settings or a configured
`version_source`, those values become the defaults for the apply call. Passing
`version_source=` explicitly still wins.

## Custom version sources

A version source is any object implementing the two-method protocol below:

```python
class VersionSource:
    def read_live_version(self, conn, config) -> str | None: ...
    def record_applied(self, conn, config, *, version, sha256, filename) -> None: ...
```

Set `[tool.pgpkg].version_source = "module:attribute"` to load one from the
project root, or pass an instance directly to `apply_migrations()` or
`migrate_from_artifact()`.

If your custom source fully replaces pgpkg's own tracking table, set
`writes_default_tracking = True` on the object or class. Otherwise `pgpkg`
will keep writing its default tracking row first, then call your source.
