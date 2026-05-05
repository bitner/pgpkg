# pgpkg

A small, focused PostgreSQL migration toolkit.

`pgpkg` replaces the `stageversion`, `makemigration`, and `migrate` flow
made popular by `pypgstac`, but in a reusable form with zero project-specific
code. You own:

- an **ordered `sql/` directory** that describes the exact state the database
  should be in, and
- `sql/pre/` and `sql/post/` directories whose contents run around every
  migration (roles, grants, settings).

`pgpkg` does everything else:

- **stageversion** — renders `sql/` into `<prefix>--<version>.sql`
- **makemigration** — diffs two staged versions into `<prefix>--<from>--<to>.sql`
  using `results.temporary_local_db` + `results.schemadiff_as_sql`
- **graph** / **plan** — show the version graph and the shortest path to a
  target version
- **migrate** — apply the plan inside one transaction with an advisory lock,
  tracking applied versions in `pgpkg.migrations`
- **verify** — round-trip every edge `a -> b` through two temp DBs and confirm
  `base(a) + a→b = base(b)`
- **wheel** — scaffold a tiny wrapper Python project that bakes the staged
  artifacts into a wheel + console script
- **bundle** — emit a raw `tar.zst` artifact with migrations plus pre/post SQL

## Install

```bash
uv tool install pgpkg                    # core
uv tool install --with 'pgpkg[diff]' pgpkg   # + results for makemigration/verify
```

## Look around

- [Quickstart](quickstart.md)
- [Project layout](layout.md)
- [CLI reference](cli.md)
- [Python API](api.md)
- [Wrapping into a wheel](wrapper.md)
- [Architecture](architecture.md)
