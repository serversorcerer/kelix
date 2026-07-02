"""Mirror tracker issues into the backlog (inbound) — the loop's SoT stays
`.kelix/backlog.md`. Outbound status/PR pushes are triggered by the runner.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ..backlog import Task, parse_backlog, serialize_backlog
from .base import InboundIssue

log = logging.getLogger(__name__)


def _task_id_for(issue: InboundIssue) -> str:
    # Use the tracker identifier so branches auto-link (kelix/<id>-<slug>).
    return issue.identifier


def mirror_inbound(backlog_path: Path, issues: list[InboundIssue]) -> int:
    """Add tracker issues as owner-authored tasks. Idempotent by task id.
    Returns count added. Never raises on tracker content."""
    existing_text = backlog_path.read_text(encoding="utf-8") if backlog_path.is_file() else ""
    existing = parse_backlog(existing_text)
    existing_ids = {t.id for t in existing}
    added: list[Task] = []
    for issue in issues:
        task_id = _task_id_for(issue)
        if task_id in existing_ids:
            continue
        added.append(
            Task(
                id=task_id,
                title=issue.title or "(untitled tracker issue)",
                priority=issue.priority,
                status="ready",
                by="owner",  # tracker issues are owner intent
                notes={"rationale": f"synced from tracker issue {issue.identifier} (data)"},
            )
        )
        existing_ids.add(task_id)
    if added:
        with backlog_path.open("a", encoding="utf-8") as fh:
            fh.write("\n## Synced from tracker\n\n" + serialize_backlog(added))
    return len(added)
