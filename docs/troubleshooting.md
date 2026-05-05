# Troubleshooting

## Docker not available in integration tests

Symptom:
- Integration tests are skipped or fail to start a PostgreSQL container.

Checks:

```bash
docker ps
uv run pytest tests/integration -q
```

Fix:
- Ensure Docker daemon is running.
- If Docker is intentionally unavailable, run only unit tests:

```bash
uv run pytest tests/unit -q
```

## Database connection issues during migrate

Symptom:
- `pgpkg migrate` fails to connect.

Checks:

```bash
env | rg '^PG(HOST|PORT|DATABASE|USER|PASSWORD|SSLMODE)'
pgpkg info --json
```

Fix:
- Pass explicit connection flags (`-h -p -d -U`) or `--dsn`.
- Verify credentials and network access to PostgreSQL.

## `makemigration` fails due to missing `results`

Symptom:
- Diff generation errors or command not found for `results` path.

Fix:

```bash
uv tool install --with 'pgpkg[diff]' pgpkg
# or in this repo
uv sync --extra diff
```

## `version_source` import or validation fails

Symptom:
- `pgpkg migrate` exits with a config error about `module:attribute` syntax,
	import failure, or missing required callables.

Checks:

```bash
pgpkg info --json
python -c "import mymodule; print(mymodule)"
```

Fix:
- Set `[tool.pgpkg].version_source` to `module:attribute`.
- Ensure the module is importable from the project root or installed in the
	runtime environment.
- Implement both `read_live_version(...)` and `record_applied(...)`.

## `pgpkg wheel` rejects projects using `version_source`

Symptom:
- Wrapper scaffolding exits with `error [E_WRAP]` mentioning `version_source`.

Cause:
- Generic wrappers cannot construct your project-specific runtime object.

Fix:
- Use `pgpkg bundle --output ...` or `pgpkg.api.bundle_project(...)` to build
	the artifact.
- Ship a custom wrapper package that calls
	`pgpkg.api.migrate_from_artifact(..., version_source=...)`.

## Release workflow version mismatch

Symptom:
- Publish workflow fails with version mismatch guard.

Cause:
- GitHub release tag and built package version differ.

Fix:
- Confirm `src/pgpkg/__init__.py::__version__`.
- Re-tag release as `v<version>` to match built artifact.

## Publish workflow fails with `invalid-publisher`

Symptom:
- The `Publish` workflow reaches the PyPI/TestPyPI publish step, then fails
	during trusted-publisher exchange.

Checks:
- Verify the trusted publisher is configured for repository `bitner/pgpkg`.
- Verify the workflow filename matches `publish-pypi.yml`.
- Verify the environment name matches `testpypi` or `pypi` exactly.

Fix:
- Update the trusted publisher entry in PyPI/TestPyPI so the repository,
	workflow, and environment fields exactly match the GitHub workflow.
