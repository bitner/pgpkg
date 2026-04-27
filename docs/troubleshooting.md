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
pip install 'pgpkg[diff]'
# or in this repo
uv sync --extra diff
```

## Session-recall shows little or no context

Symptom:
- `session-recall files --json --limit 10` returns zero files.

Cause:
- Cold-start corpus (not enough historical sessions yet).

Fix:
- Keep using baseline recall commands each session.
- Complete several real edit sessions; corpus quality improves over time.
- Verify health:

```bash
session-recall health
```

## Release workflow version mismatch

Symptom:
- Publish workflow fails with version mismatch guard.

Cause:
- GitHub release tag and built package version differ.

Fix:
- Confirm `src/pgpkg/__init__.py::__version__`.
- Re-tag release as `v<version>` to match built artifact.
