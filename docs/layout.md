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
| `pre_dir` | `sql/pre` | pre hooks |
| `post_dir` | `sql/post` | post hooks |
| `tracking_schema` | `pgpkg` | reserved, stores `migrations` table |
| `tracking_table` | `migrations` | reserved |

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

`pgpkg` owns the `pgpkg.migrations` table:

```sql
CREATE TABLE pgpkg.migrations (
    id          serial PRIMARY KEY,
    version     text NOT NULL,
    applied_at  timestamptz NOT NULL DEFAULT now(),
    sha256      text NOT NULL,
    filename    text NOT NULL
);
```

Never write to it by hand. The `pgpkg` schema is reserved.
