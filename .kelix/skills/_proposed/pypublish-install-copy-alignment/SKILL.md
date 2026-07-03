---
name: pypublish-install-copy-alignment
description: >-
  Align install instructions and package positioning across all user-facing
  surfaces for PyPI readiness — pipx-first with git fallback, mock/live proof
  labels, and preserved value-demo README contracts. Use during PYPUBLISH doc
  tasks or when README rewrites must stay green with test_value_demo.py.
---

# PyPI publish install-copy alignment

When a package moves to PyPI, install paths and proof honesty must match on
every surface a user might read — not just README.

## 1. Touch every install surface in one sweep

Update all of these in the same phase so drift does not reappear:

| Surface | Install pattern |
|---------|-----------------|
| `README.md` | `pipx install kelix` primary; git `pip install` fallback until first PyPI release |
| `docs/index.md` | Same block as README |
| `docs/quickstart.md` | pipx in step 1; remove bare `pip install <package>` as the happy path |
| `CONTRIBUTING.md` | Separate **CLI install** (pipx) from **editable dev** (`pip install -e .`) |
| `docs/agents/{cursor,claude,codex,gemini}.md` | pipx + git fallback comment on one line |

Add a maintainer link to `docs/publishing.md` under Contributing or Project.

Developer tone: use project vocabulary (verify gate, worktree, Ralph loop) with
brief inline context — not marketing copy.

## 2. Label mock vs live proof honestly

Separate receipt types so users do not confuse scaffold demos with dogfood runs:

- **Mock adapter** receipts → link `docs/proof/value-demo.md` or sample output
- **Live adapter** receipts → link real final-report paths with date/context

Apply the same mock/live distinction on `docs/index.md` when README does.

## 3. Preserve value-demo README contracts

`tests/test_value_demo.py` locks the first-screen README. When rewriting for
developer tone, **do not** remove or relocate these within the first ~30 lines:

- Value sentence containing `well-specified goal`, `walk away`, `verified commits`
- Link to `value-demo.md`

Run before and after README edits:

```bash
pytest tests/test_value_demo.py::test_readme_first_screen_value_sentence_and_demo_link -q
pytest tests/test_value_demo.py -q
```

Optional sections (Kiro, fleet) may move below the fold or be marked optional.

## 4. Sync package description metadata

PyPI, GitHub Pages, and search snippets should match:

- Copy `pyproject.toml` `[project].description` verbatim into `docs/_config.yml`
  `description` (Jekyll site)
- Keep agent-agnostic positioning: name all supported agents; cite deepest
  integration (e.g. Kiro) without making it sole identity
- No em-dashes — match pyproject punctuation exactly

## 5. Verify copy alignment

```bash
pytest tests/test_value_demo.py tests/test_doc_drift.py -q
pytest -q
ruff check src tests
```

Grep guard — agent guides must not regress to bare PyPI-less install:

```bash
rg 'pip install kelix' docs/agents/   # expect zero matches
```

Doc-only tasks still run the full test suite; value-demo and doc-drift gates
must pass before marking PUB4–PUB7-style tasks done.
