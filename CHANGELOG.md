# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-05-05

### Added
- Core migration toolkit commands: `stageversion`, `makemigration`, `graph`, `migrate`, `wheel`, `bundle`, `info`, `verify`.
- Python API facade for staging, planning, migration, and verification flows.
- Wrapper scaffold flow with bundled migration artifact (`tar.zst`) and sample wrapper project.
- Runtime tracking configuration via `[tool.pgpkg.tracking]` and pluggable `version_source` support for application-owned version tables.
- `stageversion --also-write` plus `makemigration --prepend-file`, `--append-file`, and `--append-sql` for custom packaging and wrapper migration flows.
- Deterministic bundle artifacts that preserve tracking schema/table and configured version-source metadata.
- Unit and integration test suites plus wrapper end-to-end test.
- MkDocs documentation site with architecture, API, CLI, layout, and quickstart guides.
- CI workflows for quality/unit/integration+build/docs and release publishing.

### Changed
- Documentation now standardizes install and release examples on `uv` and documents custom tracking/runtime packaging constraints.
- Publish workflow hardened with wheel install smoke test before publish.
- Publish workflow now smoke-tests a generated wrapper package before uploading distributions.
- Publish workflow checks release tag/version parity before PyPI publish.
- Docs deployment workflow aligned to main-branch release path and updated Pages action versions.
- Integration tests now support configurable PostgreSQL image for CI matrix validation.

### Fixed
- Tracking writes now survive migration SQL that changes the active database role.

### Security
- Trusted publishing workflow configured for TestPyPI/PyPI environments.

[0.1.0]: https://github.com/bitner/pgpkg/releases/tag/v0.1.0
