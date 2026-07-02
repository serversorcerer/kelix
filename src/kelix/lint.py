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

INPUT_QUALITY_TAGLINE = "Gold in, diamonds out."

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


def finding_fix(finding: Finding) -> str:
    """One-line actionable fix for a lint finding (REQ-VS4)."""
    rule = finding.rule
    if rule == "missing_details":
        return "add details: with a test path"
    if rule == "no_acceptance_signal":
        return "add a test path, assert, or exit-code evidence to details:"
    if rule == "unfalsifiable_wording":
        match = re.search(r"use '([^']+)'", finding.message)
        word = match.group(1) if match else "banned word"
        return f"remove unfalsifiable word {word} in details"
    if rule == "multiple_deliverables":
        return "split into separate tasks — remove ' and then ' from details:"
    if rule == "title_too_long":
        return "shorten title to 80 characters or fewer"
    if rule == "dangling_dep":
        return "fix deps: to reference an existing task id"
    if rule == "cyclic_deps":
        return "break the dependency cycle in deps:"
    if rule == "backlog_missing":
        return "create .kelix/backlog.md with parseable tasks"
    if rule == "roadmap_missing":
        return "create .kelix/roadmap.md with milestones, phases, and REQs"
    if rule == "roadmap_empty":
        return "add milestones, phases, and REQ bullets to .kelix/roadmap.md"
    if rule == "not_proposed":
        return "set status: proposed on kelix-authored draft tasks"
    if rule == "uncovered_req":
        return "add a backlog task with req: covering the uncovered REQ"
    if rule == "non_planning_change":
        return "limit plan iteration edits to roadmap, backlog, and phase files"
    return "edit the backlog task to satisfy the lint rule"


def format_actionable_finding(finding: Finding) -> str:
    """Task id, rule, message, and one-line fix (REQ-VS4)."""
    return f"{format_finding(finding)}\n  fix: {finding_fix(finding)}"


# Inline good/bad examples for the run spec-gate (REQ-GD1).
SPEC_GATE_EXAMPLES: dict[str, tuple[str, str]] = {
    "missing_details": (
        "- [ ] T1: demo task | priority: 50 | status: ready | by: owner",
        "- [ ] T1: JSON persistence | priority: 80 | status: ready | by: owner\n"
        "  details: save/load round-trip in tests/test_persistence.py",
    ),
    "no_acceptance_signal": (
        "  details: make the module nicer and refactor things",
        "  details: add src/kelix/foo.py; round-trip test in tests/test_foo.py",
    ),
    "unfalsifiable_wording": (
        "  details: improve the CLI experience",
        "  details: improve CLI startup to under 100ms; assert in tests/test_cli.py",
    ),
    "multiple_deliverables": (
        '  details: add foo.py and then add bar.py',
        "  details: add foo.py; tests/test_foo.py — split bar into its own task",
    ),
    "title_too_long": (
        "- [ ] T1: " + "x" * 81 + " | priority: 50 | status: ready | by: owner",
        "- [ ] T1: short title | priority: 50 | status: ready | by: owner\n"
        "  details: change in tests/test_x.py",
    ),
    "dangling_dep": (
        "- [ ] T1: work | priority: 50 | status: ready | by: owner | deps: MISSING",
        "- [ ] T1: work | priority: 50 | status: ready | by: owner | deps: T0\n"
        "  details: implement in tests/test_t1.py",
    ),
    "cyclic_deps": (
        "T1 deps T2, T2 deps T1 — both status: ready",
        "break the cycle: one task depends on the other only",
    ),
}


def format_spec_gate_findings(findings: list[Finding]) -> list[str]:
    """Actionable spec-gate output with one good/bad example per rule."""
    lines = [
        "spec gate: status: ready tasks must pass kelix lint before kelix run",
        INPUT_QUALITY_TAGLINE,
        "",
    ]
    seen_rules: set[str] = set()
    for finding in findings:
        lines.append(format_actionable_finding(finding))
        if finding.rule in seen_rules:
            continue
        seen_rules.add(finding.rule)
        examples = SPEC_GATE_EXAMPLES.get(finding.rule)
        if examples:
            bad, good = examples
            lines.append(f"  bad:  {bad}")
            lines.append(f"  good: {good}")
    return lines


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

    ``scope`` is ``"active"`` (default: all non-done tasks), ``"ready"`` (only
    ``status: ready`` tasks — run spec-gate), or ``"proposed"`` (only kelix-
    authored proposed tasks, for draft-plan validation).
    """
    findings: list[Finding] = []
    task_ids = {task.id for task in tasks}
    deps_map = {task.id: task.deps for task in tasks}

    lint_tasks = tasks
    if scope == "ready":
        lint_tasks = [t for t in tasks if t.status == "ready"]
    elif scope == "proposed":
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
        if scope == "ready" and task.status != "ready":
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


def _kelix_proposed_field_changed(before: Task, after: Task) -> bool:
    if before.notes.get("details", "") != after.notes.get("details", ""):
        return True
    if before.notes.get("rationale", "") != after.notes.get("rationale", ""):
        return True
    return before.deps != after.deps


def kelix_proposed_edits(before: list[Task], after: list[Task]) -> list[Task]:
    """Kelix proposed tasks added or with details/rationale/deps changed."""
    before_map = {task.id: task for task in before}
    edited: list[Task] = []
    for task in after:
        if task.by != "kelix" or task.status != "proposed":
            continue
        prev = before_map.get(task.id)
        if prev is None or _kelix_proposed_field_changed(prev, task):
            edited.append(task)
    return edited


def aggregate_lint_rules(findings: list[Finding]) -> dict[str, int]:
    """Count findings by rule id."""
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.rule] = counts.get(finding.rule, 0) + 1
    return counts


def lint_backlog_edits(before: list[Task], after: list[Task]) -> dict[str, int]:
    """Lint kelix proposed backlog edits; return ``{rule_id: count}``."""
    edited = kelix_proposed_edits(before, after)
    if not edited:
        return {}
    findings = lint_backlog(edited, scope="active")
    return aggregate_lint_rules(findings)


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
