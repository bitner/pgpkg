# Project layout

`pgpkg` looks for exactly this layout:

```
<project_root>/
  pyproject.toml        # must contain [tool.pgpkg]
  sql/                  # EDIT FREELY — the current (unreleased) state
    001_schema.sql
    010_tables.sql
    ...
    pre/                # runs BEFORE every applied step. IMMUTABLE public API.
      001_*.sql
    post/               # runs AFTER every applied step. IMMUTABLE public API.
      999_*.sql
  migrations/           # GENERATED — never edit base files directly
    <prefix>--<version>.sql         # from `pgpkg stageversion <version>`
    <prefix>--<from>--<to>.sql      # from `pgpkg makemigration`
```

## `[tool.pgpkg]` keys

| key | default | purpose |
|---|---|---|
| `project_name` | *(required)* | identifies the project in pgpkg.migrations and in filenames |
| `prefix` | `project_name` | file prefix for `<prefix>--<version>.sql` |
| `sql_dir` | `sql` | path to the source tree |
| `migrations_dir` | `migrations` | where staged base files + incrementals live |
| `version_source` | *(unset)* | `module:attribute` loader for a custom live-version source |

Derived paths are not configurable separately:

- `pre_dir` is always `<sql_dir>/pre`.
- `post_dir` is always `<sql_dir>/post`.

Tracking settings live under a nested table:

| key | default | purpose |
|---|---|---|
| `[tool.pgpkg.tracking].schema` | `pgpkg` | schema for pgpkg's default tracking table |
| `[tool.pgpkg.tracking].table` | `migrations` | table for pgpkg's default tracking rows |

Example:

```toml
[tool.pgpkg]
project_name = "myext"
prefix = "myext"
version_source = "myext.db:version_source"

[tool.pgpkg.tracking]
schema = "ops"
table = "schema_versions"
```

`version_source` must resolve to an object or zero-argument class with
`read_live_version(conn, config)` and
`record_applied(conn, config, *, version, sha256, filename)` methods. The
module is imported relative to the project root.

`[tool.pgpkg].pre_post_in_base` is intentionally rejected in `0.1.x`.
Keep pre/post SQL as runtime hooks or handle baked-in behavior in a custom
wrapper.

## Filename grammar

Base files:    `<prefix>--<version>.sql`
Incrementals:  `<prefix>--<from>--<to>.sql`

`<version>` is either a PEP 440 version string (`0.1.0`, `1.0.0rc1`) or the
literal `unreleased`, which always sorts last.

## Immutability

- Files under `sql/` change every commit — that's the point.
- Files under `migrations/` are immutable once released. Editing a released
  base file breaks `verify` and reproducibility for downstream consumers.
- `sql/pre/*` and `sql/post/*` run around every migration — treat their
  interface as a public API.

## Tracking table

By default, `pgpkg` owns the `pgpkg.migrations` table:

```sql
CREATE TABLE pgpkg.migrations (
    id          serial PRIMARY KEY,
    version     text NOT NULL,
    applied_at  timestamptz NOT NULL DEFAULT now(),
    sha256      text NOT NULL,
    filename    text NOT NULL
);
```

Never write to it by hand. If you configure a custom `version_source`, that
source becomes the authoritative runtime view; pgpkg's own tracking table can
still be kept in sync unless the source declares `writes_default_tracking = True`.
