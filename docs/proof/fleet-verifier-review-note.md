# Fleet branch review — session 2 (R1)

**Reviewer:** verifier (`kalph/run-20260702-011559-verifier-1`)  
**Reviewed:** `git log main..<branch> -p` on the three fleet branches below.  
**Method:** diff review + `git merge-tree` conflict simulation + pytest in each worktree.  
**No merges/rebases performed** (per task scope).

## Summary

| Branch | Commits (main..HEAD) | Library changes | Tests | pytest |
|--------|----------------------|-----------------|-------|--------|
| `kalph/run-20260702-011124-builder-1` | F1, S1, retrospective | priority field, `by_priority()`, JSON | +4 tests | 32 passed |
| `kalph/run-20260702-011125-verifier-1` | F2, retrospective | tags field, `with_tag()`, JSON | +7 tests | 35 passed |
| `kalph/run-20260702-011127-scribe-1` | V1, retrospective | CLI error handling only | +5 tests (new file) | 33 passed |

All three branches pass pytest in their isolated worktrees.

---

## builder-1 (`kalph/run-20260702-011124-builder-1`)

### What changed

**F1 — priority support**

- `Task.priority: int = 0` in `tasklite/models.py`
- `Store.add(..., priority=0)` and `Store.by_priority()` (desc priority, asc id) in `tasklite/store.py`
- JSON save/load round-trips `priority`; load uses `task.get("priority", 0)` for backward compat

**S1 — documentation**

- New `CHANGELOG.md` (Keep a Changelog format, documents 0.1.0 including priority)
- README Development section (venv pytest command)

Also updates `.kalph/backlog.md`, `.kalph/memory/project.md`, `.kalph/fleet.toml` (fleet metadata).

### Test coverage (F1)

Adequate for the feature scope:

- `test_task_priority_defaults_to_zero` — model default
- `test_add_accepts_priority` — store API
- `test_by_priority_sorts_descending_then_id_ascending` — sort tie-breaking by id
- `test_save_and_load_round_trip_priority` — JSON round-trip + `by_priority()` preserved

**Gap (minor):** unlike F2 on verifier-1, there is no explicit test loading legacy JSON **without** a `priority` key. The `task.get("priority", 0)` default is correct but untested.

### Quality notes

- Sort semantics are clear and tested (priority desc, id asc for ties).
- S1 CHANGELOG accurately describes F1; tags are not mentioned (expected — tags live on verifier-1).

---

## verifier-1 (`kalph/run-20260702-011125-verifier-1`)

### What changed

**F2 — tags support**

- `Task.tags: list[str] = field(default_factory=list)` (+ `field` import)
- `Store.add(..., tags=None)` copies tags into task
- `Store.with_tag(tag)` filters by membership
- JSON save/load round-trips `tags`; load uses `task.get("tags", [])`
- Legacy JSON without `tags` field tested explicitly

### Test coverage (F2)

Strong coverage:

- Model default, add with/without tags, `with_tag` match and no-match
- Round-trip persistence + legacy file without `tags`

No issues found in test design.

---

## scribe-1 (`kalph/run-20260702-011127-scribe-1`)

### What changed

**V1 — CLI edge-case tests**

- New `tests/test_cli_edge.py` (5 tests)
- Small **required** CLI fixes in `tasklite/cli.py`:
  - Reject empty/whitespace-only titles on `add` (exit 1, stderr message, no file written)
  - Catch `KeyError` on `done`/`remove` for missing ids (exit 1, `error: task {id} not found`)

### Test coverage (V1)

All specified scenarios covered. Tests assert exit codes, stderr content, and store unchanged on failure — good.

**Note:** CLI changes are orthogonal to F1/F2; no conflicts in `tasklite/` library files.

---

## Expected merge conflicts

Simulated with `git merge-tree $(git merge-base main <A>) <A> <B>`.

### builder-1 + verifier-1 (F1 + F2) — **heavy conflicts**

Both touch the same files with overlapping hunks:

| File | Conflict nature |
|------|-----------------|
| `tasklite/models.py` | Both add a new field after `due`; verifier also adds `field` import |
| `tasklite/persistence.py` | Both add a key in save dict and load kwargs |
| `tasklite/store.py` | Conflicting `add()` signatures (`priority=` vs `tags=`); verifier adds `with_tag()` cleanly after search |
| `tests/test_models.py` | Both append a default-value test at EOF |
| `tests/test_persistence.py` | Both append round-trip tests at EOF |
| `tests/test_store.py` | Both append store tests at EOF |
| `.kalph/backlog.md` | Task status lines differ |
| `.kalph/memory/project.md` | Priority vs Tags sections + run retrospective headers |

**Resolution guidance:** keep **both** fields everywhere:

```python
# models.py — combined
from dataclasses import dataclass, field

@dataclass
class Task:
    ...
    priority: int = 0
    tags: list[str] = field(default_factory=list)

# store.py add() — combined signature
def add(self, title, due=None, priority=0, tags=None) -> Task:
    ...
    priority=priority,
    tags=list(tags) if tags else [],
```

Persistence save/load must include both `"priority"` and `"tags"`. Test files: keep all tests from both branches (no overlap in test function names).

### builder-1 + scribe-1 — **light conflicts**

- `.kalph/backlog.md` — V1 marked done vs builder backlog state
- `.kalph/memory/project.md` — CLI notes + run retrospective sections
- **No conflicts** in `tasklite/models.py`, `store.py`, `persistence.py`, or store/model tests
- `tasklite/cli.py` and `tests/test_cli_edge.py` merge cleanly (added only on scribe)

### verifier-1 + scribe-1 — **light conflicts**

Same as builder + scribe: only `.kalph/backlog.md` and `.kalph/memory/project.md`.

---

## Recommended merge order

1. **`kalph/run-20260702-011127-scribe-1` (V1)** first — orthogonal CLI work; merges into main (or integration branch) with only kalph-metadata conflicts. Brings error handling before feature merges land CLI-facing behavior.

2. **`kalph/run-20260702-011124-builder-1` (F1 + S1)** second — establishes `priority` and ships CHANGELOG/README. Conflicts with scribe are metadata-only.

3. **`kalph/run-20260702-011125-verifier-1` (F2)** last — **rebase onto post-F1 tip** (do not force-push). Resolve the eight-file conflict set by combining priority + tags as above. Run full pytest after resolution; expect ~39 library tests once combined (32 + 7 − overlap base).

Do **not** merge F1 and F2 in parallel without rebasing — both edit the same `add()` signature and Task fields.

---

## Additional fleet context

- Newer worktrees exist (`kalph/run-20260702-011600-builder-1` has F3 `Store.clear_done()`; `kalph/run-20260702-011601-scribe-1` exists) — out of scope for this R1 review but F3 should rebase after F1+F2 integration.
- `gh pr list` unavailable in this environment; review based on local branches only.
- Episode digest confirms F1, F2, V1, S1 were independently verified in their runs.

## Verdict

All three reviewed branches are **merge-ready individually** (tests pass, scope matches backlog). The integration risk is concentrated in **F1+F2**; plan an explicit combined merge with the resolution pattern above. Consider adding a legacy JSON load test for missing `priority` during integration.
