from pathlib import Path

import pytest

from kelix.backlog import parse_backlog
from kelix.kiro import import_spec, parse_spec_tasks

SPEC_TASKS = """\
# Implementation Plan

- [ ] 1. Set up data model
- [ ] 2. Build API | with a pipe in the title
- [x] 3. Already done in spec
- [ ] 4. Write docs
Some prose that is not a task.
"""


def _repo_with_spec(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    (root / ".kiro" / "specs" / "user-auth").mkdir(parents=True)
    (root / ".kiro" / "specs" / "user-auth" / "tasks.md").write_text(SPEC_TASKS)
    (root / ".kelix").mkdir()
    (root / ".kelix" / "backlog.md").write_text("# Backlog\n")
    return root


def test_parse_spec_tasks_checkboxes_and_sanitization():
    items = parse_spec_tasks(SPEC_TASKS)
    assert len(items) == 4
    assert items[0] == (False, "Set up data model")
    # Pipes are neutralized so they cannot inject extra task fields.
    assert "|" not in items[1][1]
    assert items[2][0] is True


def test_import_spec_appends_owner_tasks_in_order(tmp_path):
    root = _repo_with_spec(tmp_path)
    count = import_spec(root, "user-auth")
    assert count == 3  # the [x] item is skipped
    tasks = parse_backlog((root / ".kelix" / "backlog.md").read_text())
    imported = [t for t in tasks if t.id.startswith("user-auth-")]
    assert len(imported) == 3
    assert all(t.by == "owner" for t in imported)
    assert all(t.status == "ready" for t in imported)
    # Spec order is preserved via priorities and dependency chaining.
    assert imported[0].priority > imported[1].priority > imported[2].priority
    assert imported[1].deps == [imported[0].id]
    assert imported[2].deps == [imported[1].id]


def test_import_spec_idempotent(tmp_path):
    root = _repo_with_spec(tmp_path)
    assert import_spec(root, "user-auth") == 3
    assert import_spec(root, "user-auth") == 0


def test_import_spec_missing_file(tmp_path):
    root = _repo_with_spec(tmp_path)
    with pytest.raises(FileNotFoundError):
        import_spec(root, "nope")
