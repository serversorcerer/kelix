---
name: wire-pypi-trusted-publishing
description: >-
  Wire PyPI trusted publishing for a Python CLI package: modern pyproject
  metadata, tag-triggered publish workflow, per-PR wheel smoke in CI, and an
  owner runbook with no secrets. Use when adding PyPI release automation or
  fixing twine check / setuptools license deprecation warnings.
---

# Wire PyPI trusted publishing

Automate build, check, upload, and wheel smoke in CI; document one-time owner
setup separately. Kelix cannot click PyPI or GitHub environment UIs.

## 1. Modernize pyproject.toml metadata

Before first upload, fix metadata so `twine check` passes without setuptools
license warnings:

- Set SPDX `license = "Apache-2.0"` (or your SPDX id) under `[project]`
- Add `license-files = ["LICENSE"]`
- Remove deprecated `[project.license]` table and `License :: …` classifier
- Add `[project.urls]` entries: `Repository`, `Issues` (and `Homepage` /
  `Documentation` as needed)
- Keep `version` in sync with the package `__version__` (both must bump on release)
- Avoid em-dashes in `description` — use a period; long descriptions feed PyPI and
  doc-site metadata verbatim

Local verify:

```bash
python -m build && twine check dist/*
pytest -q
ruff check src tests
```

## 2. Add `.github/workflows/publish.yml`

Tag-triggered upload with OIDC — no long-lived PyPI API token in secrets.

Required elements:

| Element | Value |
|---------|-------|
| Trigger | `push.tags: ["v*"]` |
| Permissions | `contents: read`, `id-token: write` |
| Job environment | `pypi` (matches PyPI trusted publisher environment name) |
| Steps | checkout → setup-python → `pip install build twine` → `python -m build` → `twine check dist/*` → wheel smoke → publish action |

Wheel smoke before upload (catches broken console scripts):

```yaml
- name: Smoke test wheel
  run: |
    pip install dist/*.whl
    kelix --help   # replace with your CLI entry point
- name: Publish to PyPI
  uses: pypa/gh-action-pypi-publish@release/v1
```

Header comments in the workflow file should list trusted-publisher fields
(owner, repo, workflow filename, environment) and point to the runbook.

## 3. Add a `package` job to CI

Every PR should build and smoke-test the wheel — not only on tag push:

```yaml
package:
  runs-on: ubuntu-latest
  steps:
    # checkout, setup-python, build, twine check, pip install dist/*.whl, CLI --help
```

This catches packaging regressions before a maintainer tags a release.

## 4. Write `docs/publishing.md` (owner runbook)

Document steps Kelix cannot automate:

1. **PyPI trusted publisher** — table of fields: project name, GitHub owner,
   repository, workflow filename (`publish.yml`), environment name (`pypi`)
2. **GitHub `pypi` environment** — create under Settings → Environments; no
   secrets required for OIDC
3. **Optional TestPyPI** — build/check/upload/install commands with a warning
   never to commit tokens
4. **Release checklist** — version bump (both `pyproject.toml` and
   `__init__.py`), commit, `git tag vX.Y.Z && git push origin vX.Y.Z`, verify
   PyPI page, `pipx install <package>` smoke
5. **Owner vs CI table** — who bumps version, who pushes tags, what CI does

Link the runbook from README under Contributing / maintainer notes. Do not
store API tokens or passwords in the doc.

## 5. Verify

```bash
pytest -q
ruff check src tests
python -m build && twine check dist/*
```

Confirm `publish.yml` references `pypa/gh-action-pypi-publish` and `v*` tags.
Hand off to **packaging-regression-gate** to lock these invariants in CI tests.
