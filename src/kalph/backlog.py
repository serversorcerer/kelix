"""Parse and serialize `.kalph/backlog.md` task lists."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

TASK_LINE = re.compile(
    r"^- \[([ x])\] (\S+): (.+?) \| priority: (\d+) \| status: (\w+) \| by: (\w+)"
    r"(?: \| deps: (.+))?$"
)
NOTE_LINE = re.compile(r"^  (rationale|details|diagnosis): (.*)$")


@dataclass
class Task:
    id: str
    title: str
    priority: int
    status: str
    by: str
    deps: list[str] = field(default_factory=list)
    notes: dict[str, str] = field(default_factory=dict)


def parse_backlog(text: str) -> list[Task]:
    """Parse backlog markdown into tasks. Malformed lines are skipped."""
    tasks: list[Task] = []
    current: Task | None = None

    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue

        match = TASK_LINE.match(line)
        if match:
            checked, task_id, title, priority, status, by, deps_raw = match.groups()
            if checked == "x" and status != "done":
                status = "done"
            deps = (
                [part.strip() for part in deps_raw.split(",") if part.strip()]
                if deps_raw
                else []
            )
            current = Task(
                id=task_id,
                title=title,
                priority=int(priority),
                status=status,
                by=by,
                deps=deps,
            )
            tasks.append(current)
            continue

        note_match = NOTE_LINE.match(line)
        if note_match and current is not None:
            key, value = note_match.groups()
            current.notes[key] = value

    return tasks


def serialize_backlog(tasks: list[Task]) -> str:
    """Serialize tasks to backlog markdown (task lines + optional notes)."""
    lines: list[str] = []
    for task in tasks:
        checkbox = "x" if task.status == "done" else " "
        parts = [
            f"- [{checkbox}] {task.id}: {task.title}",
            f"priority: {task.priority}",
            f"status: {task.status}",
            f"by: {task.by}",
        ]
        if task.deps:
            parts.append(f"deps: {','.join(task.deps)}")
        lines.append(" | ".join(parts))
        for key in ("rationale", "details", "diagnosis"):
            if key in task.notes:
                lines.append(f"  {key}: {task.notes[key]}")
    return "\n".join(lines) + ("\n" if lines else "")


def select_next(tasks: list[Task]) -> Task | None:
    """Return the highest-priority ready task whose dependencies are done.

    Owner-authored tasks outrank kalph-proposed tasks regardless of priority.
    """
    done_ids = {task.id for task in tasks if task.status == "done"}

    def ready(task: Task) -> bool:
        return task.status == "ready" and all(dep in done_ids for dep in task.deps)

    candidates = [task for task in tasks if ready(task)]
    if not candidates:
        return None

    def sort_key(task: Task) -> tuple[int, int]:
        owner_rank = 0 if task.by == "owner" else 1
        return (owner_rank, -task.priority)

    return min(candidates, key=sort_key)
