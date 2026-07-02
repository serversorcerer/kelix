"""Kiro integration: spec -> backlog import.

Maps `.kiro/specs/<name>/tasks.md` checklist items (Kiro's spec task format)
into Kelix backlog tasks. Spec text is treated as data: titles are imported
verbatim as task titles, never interpreted as instructions beyond that.
"""

from __future__ import annotations

import re
from pathlib import Path

from .backlog import Task, parse_backlog, serialize_backlog

CHECKBOX_RE = re.compile(r"^\s*-\s*\[( |x)\]\s*(?:[0-9.]+\s+)?(.+)$")

# Spec-imported tasks are owner intent: they land in the owner band of the
# rubric (docs/prioritization.md), ordered as written in the spec.
SPEC_PRIORITY_TOP = 89


def _sanitize_title(title: str) -> str:
    """Spec titles become backlog task lines; strip anything that would break
    the line format or smuggle in extra fields."""
    title = title.strip().replace("|", "/")
    title = re.sub(r"\s+", " ", title)
    return title[:200]


def parse_spec_tasks(tasks_md: str) -> list[tuple[bool, str]]:
    items = []
    for line in tasks_md.splitlines():
        m = CHECKBOX_RE.match(line)
        if m:
            items.append((m.group(1) == "x", _sanitize_title(m.group(2))))
    return items


def import_spec(root: Path, spec_name: str) -> int:
    """Append unchecked tasks from a Kiro spec to the Kelix backlog.
    Returns the number of tasks imported. Idempotent per title."""
    spec_file = root / ".kiro" / "specs" / spec_name / "tasks.md"
    if not spec_file.is_file():
        raise FileNotFoundError(f"no spec tasks file at {spec_file}")
    backlog_path = root / ".kelix" / "backlog.md"
    existing_text = backlog_path.read_text(encoding="utf-8") if backlog_path.is_file() else ""
    existing = parse_backlog(existing_text)
    existing_titles = {t.title for t in existing}
    existing_ids = {t.id for t in existing}

    slug = re.sub(r"[^a-z0-9]+", "-", spec_name.lower()).strip("-") or "spec"
    imported: list[Task] = []
    priority = SPEC_PRIORITY_TOP
    n = 1
    for done, title in parse_spec_tasks(spec_file.read_text(encoding="utf-8")):
        if done or title in existing_titles:
            continue
        task_id = f"{slug}-{n}"
        while task_id in existing_ids:
            n += 1
            task_id = f"{slug}-{n}"
        task = Task(
            id=task_id,
            title=title,
            priority=max(priority, 70),
            status="ready",
            by="owner",
            deps=[imported[-1].id] if imported else [],
            notes={"rationale": f"imported from .kiro/specs/{spec_name}/tasks.md"},
        )
        imported.append(task)
        existing_ids.add(task_id)
        priority -= 1
        n += 1

    if imported:
        serialized = serialize_backlog(imported)
        with backlog_path.open("a", encoding="utf-8") as fh:
            fh.write(f"\n## Imported from spec: {spec_name}\n\n{serialized}")
    return len(imported)
