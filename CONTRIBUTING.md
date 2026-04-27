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

3. For a smoke release, run the `Publish` workflow manually with `repository=testpypi`.

4. Verify TestPyPI install path in a clean venv:

```bash
python -m venv .venv-testpypi
. .venv-testpypi/bin/activate
python -m pip install --upgrade pip
python -m pip install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple pgpkg
pgpkg --help
```

5. Create release tag `vX.Y.Z` matching `src/pgpkg/__init__.py::__version__`.

6. Publish to PyPI by creating a GitHub Release from that tag (or by running `Publish` with `repository=pypi` only if version parity is confirmed).

## Trusted publishing setup

Before the publish workflow can work, configure trusted publishing for both environments:

- GitHub environment `testpypi` bound to the TestPyPI project
- GitHub environment `pypi` bound to the PyPI project

No API tokens are required when trusted publishing is configured correctly.

## Release policy guardrails

- The release tag version must match the built package version exactly.
- TestPyPI install smoke test is required before first PyPI publish.
- If workflow_dispatch is used for PyPI publish, confirm version parity before running it.
