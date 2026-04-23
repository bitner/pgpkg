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

1. Run the full local gate:

```bash
uv run pre-commit run --all-files
uv run ty check src tests
uv run pytest -q
uv build --out-dir dist
uv run python -m twine check dist/*
uv run mkdocs build --strict
```

2. For a smoke release, run the `Publish` GitHub Actions workflow manually with `repository=testpypi`.
3. Verify the TestPyPI install path.
4. Create a GitHub release to publish to PyPI.

## Trusted publishing setup

Before the publish workflow can work, configure trusted publishing for both environments:

- GitHub environment `testpypi` bound to the TestPyPI project
- GitHub environment `pypi` bound to the PyPI project

No API tokens are required when trusted publishing is configured correctly.

## Remaining release metadata

Before the first public release, set the real repository, documentation, and issue-tracker URLs in `pyproject.toml` once the canonical remote exists.
