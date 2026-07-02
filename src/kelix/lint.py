"""Plan and backlog lint — machine-check draft plans before promotion."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .backlog import Task, parse_backlog
from .roadmap import load_roadmap, parse_roadmap

PLAN_ARTIFACTS = (
    ".kelix/roadmap.md",
    ".kelix/backlog.md",
)

ACCEPTANCE_SIGNAL = re.compile(
    r"(?i)"
    r"(?:\btests?\b|\bassert\b|\bexit(?:s|[- ]code)?\b|\bround[- ]trip\b"
    r"|(?:tests?/|src/|[\w.-]+\.(?:py|md|toml|json|sh)\b))"
)

BANNED_PHRASES = (
    r"\bimprove\b",
    r"\bbetter\b",
    r"\bbest practices\b",
    r"\bclean up\b",
)

METRIC_SIGNAL = re.compile(
    r"(?i)"
    r"(?:\d+%?|\b(?:under|at least|no more than|within)\s+\d+"
    r"|\b\d+\s*(?:ms|s|sec|seconds|minutes|chars|bytes|lines|iterations)\b)"
)


@dataclass
class Finding:
    task_id: str
    rule: str
    message: str


def format_finding(finding: Finding) -> str:
    prefix = f"{finding.task_id}: " if finding.task_id else ""
    return f"{prefix}{finding.rule}: {finding.message}"


def _task_text(task: Task) -> str:
    parts = [task.title]
    parts.extend(task.notes.values())
    return "\n".join(parts)


def _has_acceptance_signal(text: str) -> bool:
    return bool(ACCEPTANCE_SIGNAL.search(text))


def _banned_phrase(text: str) -> str | None:
    """Return a matched banned phrase, ignoring parenthetical mentions."""
    stripped = re.sub(r"\([^)]*\)", "", text)
    for pattern in BANNED_PHRASES:
        match = re.search(pattern, stripped, re.I)
        if match:
            return match.group(0)
    return None


def _find_cycle(task_ids: set[str], deps_map: dict[str, list[str]]) -> list[str] | None:
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def dfs(node: str) -> list[str] | None:
        if node in visiting:
            start = stack.index(node)
            return stack[start:] + [node]
        if node in visited:
            return None
        visiting.add(node)
        stack.append(node)
        for dep in deps_map.get(node, []):
            if dep not in task_ids:
                continue
            cycle = dfs(dep)
            if cycle:
                return cycle
        stack.pop()
        visiting.remove(node)
        visited.add(node)
        return None

    for task_id in sorted(task_ids):
        cycle = dfs(task_id)
        if cycle:
            return cycle
    return None


def _strip_metaspec(text: str) -> str:
    """Remove parenthetical and quoted segments used to describe lint rules."""
    text = re.sub(r"\([^)]*\)", "", text)
    return re.sub(r'"[^"]*"', "", text)


def lint_backlog(tasks: list[Task], *, scope: str = "active") -> list[Finding]:
    """Check backlog tasks against the writing-for-the-loop input contract.

    ``scope`` is ``"active"`` (default: all non-done tasks) or ``"proposed"``
    (only kelix-authored proposed tasks, for draft-plan validation).
    """
    findings: list[Finding] = []
    task_ids = {task.id for task in tasks}
    deps_map = {task.id: task.deps for task in tasks}

    lint_tasks = tasks
    if scope == "proposed":
        lint_tasks = [t for t in tasks if t.by == "kelix" and t.status == "proposed"]

    cycle = _find_cycle(task_ids, deps_map)
    if cycle:
        findings.append(
            Finding(
                cycle[0],
                "cyclic_deps",
                f"dependency cycle: {' -> '.join(cycle)}",
            )
        )

    for task in lint_tasks:
        if scope == "active" and task.status == "done":
            continue

        for dep in task.deps:
            if dep not in task_ids:
                findings.append(
                    Finding(
                        task.id,
                        "dangling_dep",
                        f"dependency {dep!r} does not exist",
                    )
                )

        if len(task.title) > 80:
            findings.append(
                Finding(
                    task.id,
                    "title_too_long",
                    f"title is {len(task.title)} chars (max 80)",
                )
            )

        details = task.notes.get("details", "").strip()
        if not details:
            findings.append(
                Finding(
                    task.id,
                    "missing_details",
                    "task has no details: note with testable acceptance",
                )
            )
            continue

        text = _task_text(task)
        if " and then " in _strip_metaspec(details).lower():
            findings.append(
                Finding(
                    task.id,
                    "multiple_deliverables",
                    'details contain " and then " — split into separate tasks',
                )
            )

        if not _has_acceptance_signal(details):
            findings.append(
                Finding(
                    task.id,
                    "no_acceptance_signal",
                    "details lack test/assert/exit-code/file-named evidence",
                )
            )

        banned = _banned_phrase(text)
        if banned and not _has_acceptance_signal(details) and not METRIC_SIGNAL.search(details):
            findings.append(
                Finding(
                    task.id,
                    "unfalsifiable_wording",
                    f"details use {banned!r} without a metric or acceptance signal",
                )
            )

    return findings


def lint_repo(root: Path) -> list[Finding]:
    """Lint ``.kelix/backlog.md`` in a repository."""
    backlog_path = root / ".kelix" / "backlog.md"
    if not backlog_path.is_file():
        return [Finding("", "backlog_missing", "missing .kelix/backlog.md")]
    tasks = parse_backlog(backlog_path.read_text(encoding="utf-8"))
    return lint_backlog(tasks)


def _planning_only_changes(workdir: Path, base_sha: str) -> list[Finding]:
    """Ensure the iteration only touched planning artifacts."""
    from .gitutil import git

    if not base_sha:
        return []
    names = git(
        ["diff", "--name-only", base_sha, "HEAD"],
        workdir,
        check=False,
    ).splitlines()
    findings: list[Finding] = []
    for name in names:
        if not name:
            continue
        if name in PLAN_ARTIFACTS:
            continue
        if name.startswith(".kelix/phases/"):
            continue
        findings.append(
            Finding(
                "",
                "non_planning_change",
                f"plan iteration changed {name!r}; only roadmap/backlog/phase files allowed",
            )
        )
    return findings


def validate_plan(workdir: Path, base_sha: str = "") -> list[Finding]:
    """Validate a draft plan produced by ``kelix plan``.

    Checks roadmap parse, proposed-only kelix tasks, REQ coverage, backlog
    lint rules, and that only planning files changed.
    """
    findings: list[Finding] = []
    kelix = workdir / ".kelix"
    roadmap_path = kelix / "roadmap.md"
    backlog_path = kelix / "backlog.md"

    if not roadmap_path.is_file():
        findings.append(Finding("", "roadmap_missing", "missing .kelix/roadmap.md"))
    else:
        roadmap = parse_roadmap(roadmap_path.read_text(encoding="utf-8"))
        if not roadmap.milestones:
            findings.append(
                Finding("", "roadmap_empty", "roadmap has no milestones")
            )
        if not roadmap.phases:
            findings.append(Finding("", "roadmap_empty", "roadmap has no phases"))
        if not roadmap.reqs:
            findings.append(Finding("", "roadmap_empty", "roadmap has no REQs"))

    if not backlog_path.is_file():
        findings.append(Finding("", "backlog_missing", "missing .kelix/backlog.md"))
        return findings + _planning_only_changes(workdir, base_sha)

    tasks = parse_backlog(backlog_path.read_text(encoding="utf-8"))
    for task in tasks:
        if task.by == "kelix" and task.status != "proposed":
            findings.append(
                Finding(
                    task.id,
                    "not_proposed",
                    f"kelix-authored task {task.id!r} must have status: proposed",
                )
            )

    findings.extend(lint_backlog(tasks, scope="proposed"))

    roadmap = load_roadmap(kelix)
    if roadmap is not None:
        # A task may cover several REQs: `req: REQ-A1, REQ-A2`.
        covered = {
            part.strip()
            for task in tasks
            if task.req
            for part in task.req.split(",")
        }
        for req in roadmap.reqs:
            if req.id not in covered:
                findings.append(
                    Finding(
                        "",
                        "uncovered_req",
                        f"{req.id} is not referenced by any backlog task",
                    )
                )

    findings.extend(_planning_only_changes(workdir, base_sha))
    return findings
