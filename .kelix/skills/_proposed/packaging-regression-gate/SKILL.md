---
name: packaging-regression-gate
description: >-
  Add pytest smoke tests that lock PyPI packaging invariants — publish workflow,
  SPDX license, console script entry point, version sync, and wheel/sdist build.
  Use after wiring trusted publishing or when creating tests/test_packaging.py
  for a PYPUBLISH phase.
---

# Packaging regression gate

Encode packaging contracts in CI so metadata drift or broken builds fail tests
before a maintainer tags a release. Pair with **wire-pypi-trusted-publishing**
for the initial wiring.

## 1. Create tests/test_packaging.py

Four focused tests cover the minimum lock set:

| Test | Asserts |
|------|---------|
| `test_publish_workflow_exists` | `.github/workflows/publish.yml` exists; contains `pypa/gh-action-pypi-publish` and `v*` tag trigger |
| `test_pyproject_license_and_script_entry` | SPDX license string and `[project.scripts]` console entry point |
| `test_pyproject_version_matches_package` | `pyproject.toml` `[project].version` equals `import package; package.__version__` |
| `test_python_build_produces_wheel_and_sdist` | `python -m build` yields exactly one `.whl` and one `.tar.gz` |

Use `tomllib` to parse `pyproject.toml`. Read workflow text directly — do not
shell out to `rg`.

## 2. Build in an isolated temp copy

The build test must not assume a clean workspace or pollute `dist/`:

```python
@pytest.importorskip("build")

def test_python_build_produces_wheel_and_sdist(tmp_path):
    for name in ("pyproject.toml", "README.md", "LICENSE"):
        shutil.copy2(ROOT / name, tmp_path / name)
    shutil.copytree(ROOT / "src", tmp_path / "src")

    result = subprocess.run(
        [sys.executable, "-m", "build"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout

    dist = tmp_path / "dist"
    assert len(list(dist.glob("*.whl"))) == 1
    assert len(list(dist.glob("*.tar.gz"))) == 1
```

Adjust the copied root files if your package requires additional build inputs
(e.g. `MANIFEST.in`).

## 3. Keep version checks import-safe

Import the installed package for `__version__` only after `PYTHONPATH=src` or
a normal editable install in CI. The version test should fail when only one of
`pyproject.toml` or `__init__.py` was bumped.

## 4. Verify

```bash
pytest tests/test_packaging.py -q
pytest -q
ruff check src tests
python -m build && twine check dist/*
```

Gate is green only when packaging tests pass alongside the full suite and local
build check succeeds.

## 5. Phase handoff

After PUB8-style tests land, record the decision in `DECISIONS.md` (architecture
choice + pointer to `docs/publishing.md`) and run the phase closure gate with
build/twine included in the final verify command list.
