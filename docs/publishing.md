# Publishing Kelix to PyPI

Maintainer runbook for releasing `kelix` to [PyPI](https://pypi.org/project/kelix/).
Kelix automates build, check, and upload in CI; one-time PyPI and GitHub setup
stays with the owner.

## One-time setup (owner only)

Kelix cannot click these UIs for you. Do each step once per repository.

### 1. PyPI trusted publisher

On [pypi.org](https://pypi.org) → your account → **Publishing** → **Add a new
trusted publisher** for the `kelix` project (create the project name first if
needed). Use these fields:

| Field | Value |
| --- | --- |
| PyPI project name | `kelix` |
| Owner | `serversorcerer` |
| Repository name | `kelix` |
| Workflow name | `publish.yml` |
| Environment name | `pypi` |

Trusted publishing uses GitHub OIDC — no long-lived PyPI API token in repository
secrets.

### 2. GitHub `pypi` environment

In the GitHub repo: **Settings → Environments → New environment** → name it
`pypi`. No environment secrets are required for trusted publishing. Optional:
add protection rules (required reviewers, wait timer) before the first public
release.

### 3. Optional: TestPyPI

For a dry run before the first production upload:

```bash
python -m pip install --upgrade build twine
python -m build
twine check dist/*

# One-time: register kelix on https://test.pypi.org and add a trusted publisher
# with the same owner/repo/workflow fields, environment name testpypi (or use
# __token__ API key from TestPyPI account settings — never commit tokens).
twine upload --repository testpypi dist/*
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ kelix
kelix --help
```

## Release checklist

1. **Bump version** in both places (they must match):
   - `pyproject.toml` → `[project].version`
   - `src/kelix/__init__.py` → `__version__`
2. **Commit** the version bump on `main` (or merge your release PR).
3. **Tag and push** (owner action — Kelix does not push tags):

   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```

   Use a `v*` tag; `.github/workflows/publish.yml` triggers on `push: tags: v*`.
4. **Watch CI** — workflow **Publish to PyPI** builds, runs `twine check`, smoke
   tests `kelix --help` from the wheel, then uploads via
   `pypa/gh-action-pypi-publish@release/v1`.
5. **Verify on PyPI** — open https://pypi.org/project/kelix/ and confirm the new
   version and metadata (Apache-2.0, description, URLs).
6. **Verify install** from a clean environment:

   ```bash
   pipx install kelix
   kelix --help
   ```

## What CI does vs what you do

| Step | Who |
| --- | --- |
| `python -m build`, `twine check`, wheel smoke test | `publish.yml` on tag push |
| Package job on every `main` push / PR | `ci.yml` `package` job |
| Trusted publisher + GitHub environment | Owner (one time) |
| Version bump commit | Maintainer |
| `git tag` + `git push origin vX.Y.Z` | Owner |
| Post-release pipx smoke test | Maintainer (recommended) |

## Local preflight (before tagging)

Same commands CI runs:

```bash
python -m pip install --upgrade build twine
python -m build
twine check dist/*
pip install dist/*.whl
kelix --help
```

Also run the repo verify gate: `pytest -q`, `ruff check src tests`, and
`kelix lint --path .`.

## Troubleshooting

- **Upload failed, trusted publisher error** — confirm PyPI publisher fields match
  `serversorcerer` / `kelix` / `publish.yml` / environment `pypi`, and that the
  workflow job uses `environment: pypi` (see `.github/workflows/publish.yml`).
- **Wrong version on PyPI** — tag must point at the commit that contains the
  bumped `pyproject.toml` and `__version__`; delete erroneous tags only with
  care (PyPI does not allow re-uploading the same version).
- **Metadata warnings** — fix `pyproject.toml` per [PyPA packaging
  guide](https://packaging.python.org/en/latest/tutorials/packaging-projects/);
  `twine check` should pass with zero errors before you tag.
