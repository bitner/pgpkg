# Wrapping into a wheel

Shipping a database extension or application as a Python wheel means
consumers can install and migrate without cloning the source tree:

```
pip install myext-migrator
myext-migrator migrate -h db.example.com -d prod -U deploy
```

`pgpkg wheel` scaffolds the boilerplate.

## Scaffold

```
pgpkg wheel --output-dir ../myext-migrator
```

This produces:

```
myext-migrator/
  pyproject.toml
  README.md
  src/
    myext_migrator/
      __init__.py
      cli.py
      migrations.tar.zst   # baked artifact (pgpkg.artifact.build_artifact)
      py.typed
```

- `migrations.tar.zst` contains every staged base file, every incremental,
  and the contents of `sql/pre/` + `sql/post/`, plus a `MANIFEST.json`
  with SHA-256 per entry.
- `src/myext_migrator/cli.py` is a tiny argparse CLI that calls
  `pgpkg.api.migrate_from_artifact` using the baked artifact.

## Build and install

```
cd myext-migrator
uv build
pip install dist/myext_migrator-*.whl
```

## Runtime dependency

The wrapper depends on `pgpkg>=0.1`. The wrapper wheel does *not* bundle
`psycopg`; it gets it through the pgpkg dependency.

## What the wrapper cannot do

The wrapper is apply-only:

- no `stageversion`, `makemigration`, `graph`, or `verify` — those need
  the source tree
- no ad-hoc SQL — the artifact is immutable once baked.

If you need those commands, use the base `pgpkg` CLI against the source
tree instead.

## Bundle-only (no wrapper)

If you just want the artifact file:

```
pgpkg bundle --output myext.tar.zst
```

Load it elsewhere with `pgpkg.artifact.load_artifact(path)` or
`pgpkg.api.migrate_from_artifact(path, ...)`.
