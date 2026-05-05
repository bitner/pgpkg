# GitHub + PyPI Setup Guide

This checklist takes a local `pgpkg` repository to a production-ready GitHub repository with automated TestPyPI/PyPI publishing.

## 1) Create and push the GitHub repository

1. Create an empty GitHub repo (for example, `pgpkg`).
2. Add the remote and push:

```bash
git remote add origin git@github.com:<OWNER>/pgpkg.git
git push -u origin <BRANCH>
```

3. Push all long-lived branches you want preserved.

## 2) Repository settings (recommended hygiene)

1. Enable branch protection on the default branch:
   - Require pull request before merging
   - Require status checks to pass
   - Require branches to be up to date before merging
2. Require these checks from CI:
   - `quality`
   - `unit (3.11)`
   - `unit (3.12)`
   - `unit (3.13)`
   - `integration (postgres:14-alpine)`
   - `integration (postgres:15-alpine)`
   - `integration (postgres:16-alpine)`
   - `integration (postgres:17-alpine)`
   - `build-docs`
3. Enable "Automatically delete head branches" after merge.
4. Enable Dependabot alerts and security updates.
5. In Settings -> Pages, set Source to `GitHub Actions` so `.github/workflows/docs-pages.yml` can publish the MkDocs site.

## 3) PyPI/TestPyPI account and project prerequisites

You need accounts on both sites:
- https://pypi.org
- https://test.pypi.org

Create or claim the same project name on TestPyPI first, then PyPI.

### Required access

- You must be an Owner or Maintainer for the project on both services.
- You must have admin rights on the GitHub repository to configure environments and workflows.

## 4) Preferred publishing model: Trusted Publishing (OIDC)

This repository already includes `.github/workflows/publish-pypi.yml`, which is configured for trusted publishing.

### 4a) Configure GitHub environments

Create these environments in GitHub:
- `testpypi`
- `pypi`

Optional hardening:
- Add required reviewers for `pypi` environment
- Restrict deployment branches/tags

### 4b) Configure trusted publisher on TestPyPI

In TestPyPI project settings, add a trusted publisher with:
- Owner: `<OWNER>`
- Repository: `pgpkg`
- Workflow filename: `publish-pypi.yml`
- Environment: `testpypi`

### 4c) Configure trusted publisher on PyPI

In PyPI project settings, add a trusted publisher with:
- Owner: `<OWNER>`
- Repository: `pgpkg`
- Workflow filename: `publish-pypi.yml`
- Environment: `pypi`

## 5) Credentials you actually need

With trusted publishing configured correctly:
- No PyPI API token is needed in GitHub secrets.
- No username/password is needed in CI.
- The only required "credential" in CI is GitHub's OIDC identity (`id-token: write`, already set in workflow).

You still need:
- GitHub account with repo admin rights
- PyPI/TestPyPI account with project owner/maintainer rights

## 6) Optional fallback model: API token publishing

Only use this if trusted publishing cannot be enabled.

1. Create project-scoped API tokens in PyPI and TestPyPI.
2. Add these repository secrets:
   - `PYPI_API_TOKEN`
   - `TEST_PYPI_API_TOKEN`
3. Update publish workflow to pass `password: ${{ secrets.<TOKEN_NAME> }}` to `pypa/gh-action-pypi-publish`.

## 7) First release flow

1. Run local gate:

```bash
uv run pre-commit run --all-files
uv run ty check src tests
uv run pytest -q
uv build --out-dir dist
uv run python -m twine check dist/*
uv run mkdocs build --strict
```

2. Smoke publish to TestPyPI:
   - GitHub Actions -> `Publish` -> `Run workflow` -> `repository=testpypi`
3. Verify install from TestPyPI:

```bash
uv venv /tmp/pgpkg-smoke
uv pip install --python /tmp/pgpkg-smoke/bin/python \
   -i https://test.pypi.org/simple/ \
   --extra-index-url https://pypi.org/simple \
   pgpkg
/tmp/pgpkg-smoke/bin/pgpkg --help
```

The `Publish` workflow's build job also smoke-tests a generated wrapper wheel,
so a passing TestPyPI run confirms both the base CLI wheel and the wrapper
packaging path.

4. Create a GitHub Release (tag) to trigger production PyPI publish.

## 8) Post-setup metadata cleanup

Add canonical URLs in `pyproject.toml`:

```toml
[project.urls]
Homepage = "https://github.com/<OWNER>/pgpkg"
Repository = "https://github.com/<OWNER>/pgpkg"
Documentation = "https://<OWNER>.github.io/pgpkg/"
Issues = "https://github.com/<OWNER>/pgpkg/issues"
```

## 9) Quick troubleshooting

- "invalid-publisher" or "publisher not trusted": trusted publisher fields do not exactly match repo/workflow/environment. For this repo, confirm `bitner/pgpkg`, workflow `publish-pypi.yml`, and environment `testpypi` or `pypi` exactly.
- Publish job not starting: verify environment name in workflow matches configured environment.
- Artifact missing in publish job: ensure build job used `uv build --out-dir dist` and uploaded `dist/*`.
