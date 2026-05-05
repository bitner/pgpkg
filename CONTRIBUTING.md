# Contributing

## Local setup

This repository uses `uv` for local development.

```bash
uv sync --extra dev --extra diff
uv run pre-commit install
```

## Day-to-day commands

```bash
uv run pre-commit run --all-files
uv run ty check src tests
uv run pytest -q
uv build --out-dir dist
uv run mkdocs build --strict
```

## Test split

- `tests/unit` is fast and should pass on every supported Python version.
- `tests/integration` uses Docker via `testcontainers` and validates live PostgreSQL flows.

## Releasing

1. Ensure package version is correct in `src/pgpkg/__init__.py`.

2. Run the full local gate:

```bash
uv run pre-commit run --all-files
uv run ty check src tests
uv run pytest -q
uv build --out-dir dist
uv run python -m twine check dist/*
uv run mkdocs build --strict
```

3. Create release tag `v0.1.0` matching `src/pgpkg/__init__.py::__version__`.

4. Publish to PyPI by creating a GitHub Release from that tag.

Optional manual path:
- Run `Publish` with `expected_version=0.1.0` only if version parity is already confirmed.

5. Verify the PyPI install path in a clean venv:

```bash
uv venv .venv-pypi
uv pip install --python .venv-pypi/bin/python pgpkg
.venv-pypi/bin/pgpkg --help
```

## Trusted publishing setup

Before the publish workflow can work, configure trusted publishing for the PyPI environment:

- GitHub environment `pypi` bound to the PyPI project

No API tokens are required when trusted publishing is configured correctly.

## Release policy guardrails

- The release tag version must match the built package version exactly.
- The publish build job smoke-tests both the CLI wheel and a generated wrapper before upload.
- If workflow_dispatch is used for PyPI publish, confirm version parity before running it.
