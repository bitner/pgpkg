# pgpkg Project Plan (Living)

Last updated: 2026-05-05
Owner: core maintainers
Status: Local release gate, docs refresh, and generated-wrapper smoke pass on docs/v0.1.0-release-prep; release path now targets PyPI only while TestPyPI access is unavailable

## 1) Mission

Ship a reliable PostgreSQL migration toolkit (library + CLI) that:
- stages base SQL versions from `sql/`
- generates incrementals via `results`
- plans and applies migrations safely to live DBs
- bundles migrations for wrapper projects
- publishes cleanly to PyPI with reproducible release gates

## 2) Source of Truth Rules (Read First)

- This file is a living execution plan and must be updated during active work.
- Every task here must be in one of three states: `[ ]` not started, `[-]` in progress, `[x]` done.
- Do not leave ambiguous status text like "almost done".
- Update this plan in the same PR/commit where work is performed.
- When a task is done, add one brief proof note (test result, command, or file changed).
- Before asking another model to review the project, update this file first so the next model starts from accurate state.
- After any alternate-model review, merge accepted findings back into this file immediately and convert them into checklist items.
- If the working tree contains uncommitted release-critical changes, record them in this plan explicitly.

## 3) Session-Recall Operating Loop (Required)

Before any substantial coding/review session, run:

```bash
session-recall files --json --limit 10
session-recall list --json --limit 5
```

If those are low-signal, deepen selectively:

```bash
session-recall search "<topic>" --json
session-recall show <session-id> --json
session-recall health
```

Plan update protocol per session:
1. Run the two baseline `session-recall` commands.
2. If `session-recall files` is empty, note "cold start" rather than assuming recall is broken.
3. Update this plan's "Session Log" with date + one-line summary before substantial work.
4. If using another model, paste or summarize the current checklist/status into that session.
5. Execute work.
6. Mark checklist status changes immediately.
7. Record validation evidence under the task that changed.

## 4) Current Scope (Release 0.1.x)

In scope:
- `stageversion`, `makemigration`, `graph`, `migrate`, `wheel`, `bundle`, `info`, `verify`
- Python API facade in `src/pgpkg/api.py`
- Wrapper scaffolding and sample wrapper
- Unit/integration tests and docs site
- CI, docs deployment, trusted publishing workflows

Out of scope:
- pg_tle/deb packaging and extension distro orchestration
- downgrade planning
- cross-database support
- plugin systems and custom adapter runtime hooks

## 5) Codebase Reality Check (Synced)

Implemented modules exist:
- `src/pgpkg/{api,artifact,catalog,cli,config,diff,errors,executor,layout,planner,staging,tracking,versioning,wrapper,_conn}.py`

Implemented tests exist:
- Unit: `tests/unit/*`
- Integration: `tests/integration/{test_diff,test_executor,test_tracking,test_wrapper_end_to_end}.py`
- Shared fixtures: `tests/conftest.py`, `tests/fixtures/sample_project/*`

Workflows exist:
- `ci.yml`
- `docs-pages.yml`
- `publish-pypi.yml`

Docs exist:
- `docs/{index,quickstart,layout,cli,api,wrapper,architecture}.md`

Current branch state:
- Branch: `docs/v0.1.0-release-prep`
- Divergence from `main`: ahead 5, behind 0 (`git rev-list --left-right --count main...HEAD` -> `0 5`)
- Working tree: local workflow/docs edits pending commit for the PyPI-only release path
- Remote tracking: none configured locally (`git branch -vv`)
- Branch-only files vs `main`: `.gitignore`, `CHANGELOG.md`, `README.md`, `docs/troubleshooting.md`

## 6) Completed Work Log (Up To Date)

Core implementation:
- [x] Project scaffolding and package layout complete.
- [x] Core migration pipeline complete (`stageversion` -> `makemigration` -> `migrate`).
- [x] Wrapper bundle flow complete (`wheel` + sample wrapper).
- [x] Tracking schema and migration execution path complete.
- [x] CLI command surface complete and tested.

Quality and validation:
- [x] Unit and integration test suites implemented.
- [x] Local validation passes: `85 passed` on latest run.
- [x] Packaging checks pass: wheel/sdist build + `twine check`.
- [x] Docs strict build passes (`mkdocs build --strict`).
- [x] Branch-local packaging/docs checks rerun after post-`main` docs changes.
  - Proof: `uv build --out-dir dist`, `uv run twine check dist/*`, and `uv run mkdocs build --strict` passed on 2026-04-27 on `docs/v0.1.0-release-prep`.

Release hardening recently added:
- [x] Publish workflow wheel smoke test added.
  - Proof: `.github/workflows/publish-pypi.yml` has "Smoke test wheel install".
- [x] Publish workflow release tag/version guard added.
  - Proof: `.github/workflows/publish-pypi.yml` has "Verify tag matches built version".
- [x] Docs workflow cleaned to main-only branch deploy path.
  - Proof: `.github/workflows/docs-pages.yml` push/deploy conditions target `main` only.
- [x] Docs workflow Pages action versions updated.
  - Proof: `actions/configure-pages@v6`, `upload-pages-artifact@v5`, `deploy-pages@v5`.
- [x] Latest local release validation on current tree passes.
  - Proof: `pytest`, `uv build`, `twine check`, and `mkdocs build --strict` succeeded on 2026-04-27 after workflow hardening edits.
- [x] Generated wrapper smoke path validated locally against the built `pgpkg` wheel.
  - Proof: built a sample wrapper, installed repo `dist/pgpkg-0.1.0-py3-none-any.whl` into a clean venv, then installed the generated wrapper wheel and ran `sampleext-migrator info` on 2026-05-05.

Session-recall setup:
- [x] `session-recall` installed and callable.
- [x] Copilot instructions include "Progressive Session Recall" block.
- [x] Session store now available (health command succeeds).
- [ ] Session-recall corpus warmed with useful repo-file history.
  - Current state: `files --json --limit 10` still returns 0 files; `list --json --limit 5` now returns 5 recent repo sessions; `health` reports `22 sessions` with progressive disclosure still calibrating at `86/200`.

## 7) Active Checklist (What Is Left)

### A. Multi-direction review pass
- [x] Run a second-model release review using the baseline session-recall commands first.
  - Proof: secondary reviewer run completed with actionable findings on workflow publish guardrails, metadata URLs, and supply-chain pinning risk.
- [x] Merge accepted second-model findings into this plan the same day.
  - Accepted: manual-PyPI version guard added, project URLs added, CI postgres-version matrix added.
- [x] Record rejected findings with one-line rationale to avoid repeated churn.
  - Rejected/deferred: full commit-SHA action pinning deferred to a separate supply-chain hardening pass to avoid mixing with release-candidate unblockers.

### B. Commit and remote validation
- [x] Commit current release-hardening workflow edits with a conventional commit.
  - Proof: `bff68c5 chore: harden release pipeline and release docs`, `579c2fc fix: make release smoke test uv-venv compatible`.
- [x] Push branch and verify CI/doc workflows succeed remotely.
  - Proof: CI run `25015495681` success and Docs run `25015495690` success on head `579c2fcee7683672e1893330d740e3b6f1bd7f1c`.

### C. Release candidate prep
- [x] Latest local release gate passes on current tree.
  - Proof: validated on 2026-04-27.
- [x] Re-run local release gate immediately before tagging if any code or workflow changes occur after this plan update.
  - Proof: pre-commit, ty, pytest, build, twine check, and mkdocs strict rerun passed on 2026-04-27 after metadata/docs/CI updates.
- [x] Re-ran the local release gate after runtime-config/docs refresh on this branch.
  - Proof: `uv run pre-commit run --all-files`, `uv run ty check src tests`, `uv run pytest -q`, `uv build --out-dir dist`, `uv run python -m twine check dist/*`, and `uv run mkdocs build --strict` all passed on 2026-05-05.
- [x] Create/refresh `CHANGELOG.md` with 0.1.0 release notes.
- [x] Remove TestPyPI release lane until access is available.
  - Proof: `.github/workflows/publish-pypi.yml`, `CONTRIBUTING.md`, and `GITHUB_PYPI_SETUP.md` now describe a PyPI-only release path.
- [ ] Create GitHub Release tag `v0.1.0` matching `src/pgpkg/__init__.py::__version__`.
- [ ] Publish to PyPI from the trusted publishing workflow.
- [ ] Verify install from PyPI in a clean venv and run `pgpkg --help`.

### D. Session-recall optimization
- [-] For the next 5-10 real work sessions, prepend baseline recall commands and ensure actual file edits happen in those sessions.
  - Progress: baseline recall commands were rerun on 2026-04-27 before this plan update; this session includes a real file edit to keep warming the corpus.
- [-] After each substantial session, add one short human summary to the session log in this plan.
  - Progress: this session's summary was added below; continue this habit until file recall becomes non-empty.
- [ ] Re-check after warmup:
  - `session-recall files --json --limit 10`
  - `session-recall list --json --limit 5`
  - `session-recall health`
- [ ] Target: non-empty repo file recall and improved corpus-size/progressive-disclosure signal.

### E. Nice-to-have (post-0.1.0)
- [x] Add PostgreSQL version matrix (14-17) for integration tests.
  - Proof: `ci.yml` integration job now uses `postgres:14/15/16/17-alpine` matrix with `PGPKG_TEST_POSTGRES_IMAGE`.
- [x] Add release process doc section for version bump + release/tag policy.
  - Proof: `CONTRIBUTING.md` release section updated with explicit version/tag parity and a PyPI-only publish path.
- [x] Add troubleshooting section for top migration/connectivity failure modes.
  - Proof: new `docs/troubleshooting.md` added and included in `mkdocs.yml` nav.

## 8) Definition of Done for 0.1.0

All must be true:
- [-] All release gate commands pass locally and in CI.
  - Progress: latest full gate passed locally on 2026-05-05, including `pre-commit`, `ty`, `pytest`, `uv build`, `twine check`, strict MkDocs, and generated-wrapper smoke; branch-specific remote CI has not run because this branch has no upstream.
- [x] Second-model review findings are triaged and merged into this plan.
  - Proof: accepted and rejected findings are recorded in section 7A and summarized in the 2026-04-27 session log.
- [ ] PyPI install smoke verified.
- [ ] GitHub Release tag equals package version.
- [ ] PyPI publish succeeds from trusted publishing workflow.
- [-] Session-recall baseline commands are part of team runbook and this plan-update loop is being followed.
  - Progress: section 3 defines the loop, and this session followed it before work started; keep using it through the remaining warmup sessions.

## 9) Session Log (Keep Current)

- [2026-04-27] Plan rewritten to living format; synced with current code/workflows; release-hardening tasks recorded as done.
- [2026-04-27] Added publish smoke test + tag/version guard + docs workflow cleanup; local validation re-run passed.
- [2026-04-27] Session-recall confirmed functional; corpus still cold-start and needs more sessions to become high-signal.
- [2026-04-27] Plan refreshed again for second-model review; current workflow hardening changes are local/uncommitted; baseline recall still shows cold-start with empty file recall.
- [2026-04-27] Second-model findings triaged: accepted release guardrail + metadata + matrix/doc improvements implemented; local full gate rerun passed; supply-chain SHA pinning deferred.
- [2026-04-27] Committed and pushed release hardening updates; remote CI+Docs runs are green on latest main; TestPyPI publish run failed at trusted publisher exchange (`invalid-publisher`) and requires account-level publisher config update.
- [2026-04-27] Baseline recall rerun on `docs/v0.1.0-release-prep`: repo sessions increased to 22 but file recall remains empty; current branch is clean, 2 commits ahead of `main`, has no upstream, and branch-local `uv build`, `twine check`, and strict MkDocs validation all pass.
- [2026-05-05] Baseline recall rerun for this session; docs were synced with runtime tracking/version-source behavior, the full local release gate passed (`85 passed`), and generated-wrapper smoke succeeded against the built `pgpkg` wheel.
- [2026-05-05] Removed the TestPyPI lane from workflow/docs because access is unavailable; release guidance now targets PyPI only.

## 10) Update Template (Copy For Each Future Session)

Use this block when updating the plan:

```markdown
### Session YYYY-MM-DD
- Model used:
- Recall run: files/list (yes/no), health status
- Recall quality: cold-start / useful / high-signal
- Goal:
- Work done:
- Validation evidence:
- Accepted findings from other reviewers/models:
- Rejected findings from other reviewers/models:
- Checklist updates:
  - [ ] / [-] / [x] items changed
- Next step:
```
