"""Fleet mode: N independent Kelix loops, one repo, coordination through files.

No message bus, no RPC (mission non-goal). Coordination surface:
- `.kelix/fleet/claims/<task>.json` — atomic task claims (claims.py)
- `.kelix/fleet/mailbox/*.md`       — notes between agents, read at iteration start
- `.kelix/fleet/skills/`            — shared skill discoveries
Everything `kelix status` shows is derived from these files plus git.
"""

from __future__ import annotations

import re
import threading
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .backlog import Task, parse_backlog, select_next, waves
from .claims import claim_task, list_claims, mark_claim_done
from .config import Config
from .gitutil import git
from .loop import (
    FROM_COMMIT_RATIONALE_PREFIX,
    TASK_FROM_RATIONALE_RE,
    IterationRecord,
    Runner,
    RunResult,
)
from .metrics import FleetSummaryRow, append_run_metrics
from .roadmap import coverage, load_roadmap
from .state import load_state

BUILTIN_ROLES: dict[str, str] = {
    "builder": (
        "Role: builder. Prefer feature and implementation tasks. Do not take "
        "tasks that are purely tests, docs, or fixing other agents' breakage "
        "unless nothing else is eligible."
    ),
    "verifier": (
        "Role: verifier. Prefer tasks that write or strengthen tests. Also: "
        "each iteration, look at open kelix/* branches or PRs (`git branch -a`, "
        "`gh pr list` if available); if you find problems in another agent's "
        "work, leave a review note as a new file in .kelix/fleet/mailbox/ "
        "named <timestamp>-verifier.md describing the issue and the branch. "
        "When branches conflict, rebase and flag in the mailbox — never "
        "force-resolve or force-push."
    ),
    "fixer": (
        "Role: fixer. Prefer broken builds, failing or flaky tests, and "
        "blockers other agents reported in the mailbox. Read the mailbox "
        "first every iteration."
    ),
    "scribe": (
        "Role: scribe. Prefer documentation, changelog, and retrospective "
        "tasks. Keep docs consistent with the code as it lands."
    ),
}

FLEET_ROLE_COMMON = (
    "You are one agent in a Kelix fleet. Coordination rules: work ONLY the "
    "task assigned below (it is claimed for you; other tasks may be claimed "
    "by other agents). If your work affects others (schema changes, renamed "
    "modules, API changes), leave a note file in .kelix/fleet/mailbox/ named "
    "<timestamp>-<your-role>.md. If you write a new skill, also copy it to "
    ".kelix/fleet/skills/<name>/SKILL.md so other agents see it immediately."
)

_TASK_KIND_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("test", re.compile(r"\btests?\b", re.I)),
    (
        "docs",
        re.compile(
            r"\b(docs?|documentation|changelog|readme|retrospective|planning)\b",
            re.I,
        ),
    ),
    ("fix", re.compile(r"\b(fix|broken|blocker|flake|failing)\b", re.I)),
]

ROLE_PREFERRED_KINDS: dict[str, frozenset[str]] = {
    "builder": frozenset({"feature"}),
    "verifier": frozenset({"test"}),
    "fixer": frozenset({"fix"}),
    "scribe": frozenset({"docs"}),
}


@dataclass
class FleetAgent:
    id: str
    role: str = "builder"


@dataclass
class FleetSpec:
    agents: list[FleetAgent] = field(default_factory=list)
    roles: dict[str, str] = field(default_factory=dict)  # extra/custom roles
    max_iterations: int = 10
    stale_claim_s: int = 900

    def role_prompt(self, role: str) -> str:
        custom = self.roles.get(role)
        base = custom or BUILTIN_ROLES.get(role) or f"Role: {role}."
        return base + "\n\n" + FLEET_ROLE_COMMON


class FleetError(Exception):
    pass


def load_fleet_spec(cfg: Config, config_file: str) -> FleetSpec:
    path = cfg.root / config_file
    if not path.is_file():
        raise FleetError(f"no fleet config at {config_file}")
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    spec = FleetSpec()
    fleet = raw.get("fleet", {})
    spec.max_iterations = int(fleet.get("max_iterations", spec.max_iterations))
    spec.stale_claim_s = int(fleet.get("stale_claim_s", spec.stale_claim_s))
    for entry in raw.get("agents", []):
        if "id" not in entry:
            raise FleetError("every [[agents]] entry needs an id")
        spec.agents.append(FleetAgent(id=entry["id"], role=entry.get("role", "builder")))
    for name, table in raw.get("roles", {}).items():
        prompt = table.get("prompt") if isinstance(table, dict) else None
        if prompt:
            spec.roles[name] = prompt
    if not spec.agents:
        raise FleetError("fleet config defines no agents")
    ids = [a.id for a in spec.agents]
    if len(ids) != len(set(ids)):
        raise FleetError("duplicate agent ids in fleet config")
    return spec


def _earliest_incomplete_wave(tasks: list[Task]) -> int | None:
    """Index of the first wave containing a non-done task, or None if all done."""
    wave_list, _ = waves(tasks)
    for index, wave in enumerate(wave_list):
        if any(task.status != "done" for task in wave):
            return index
    return None


def _wave_allowed_task_ids(tasks: list[Task]) -> set[str]:
    """Task ids eligible for fleet claims: only the earliest incomplete wave."""
    wave_list, _ = waves(tasks)
    earliest = _earliest_incomplete_wave(tasks)
    if earliest is None:
        return set()
    return {task.id for task in wave_list[earliest]}


def make_claim_hook(cfg: Config, spec: FleetSpec, agent_id: str):
    """pre_iteration hook: claim the next eligible task for this agent.

    Returns role-extra text pinning the claimed task, or None when no
    unclaimed, unblocked work remains (the agent's loop then completes).
    """

    def hook(workdir: Path, index: int) -> str | None:
        backlog_path = workdir / cfg.loop.plan_file
        if not backlog_path.is_file():
            return None
        tasks = parse_backlog(backlog_path.read_text(encoding="utf-8"))

        # Fleet-wide task completion lives in claim files (branches diverge,
        # claims do not): a done-claim means some agent verified that task.
        done_elsewhere = {
            c["task"] for c in list_claims(cfg.kelix_dir) if c.get("done")
        }
        for t in tasks:
            if t.id in done_elsewhere and t.status != "done":
                t.status = "done"

        # Release-on-done: mark our own completed tasks in the shared claims.
        for t in tasks:
            if t.status == "done":
                mark_claim_done(cfg.kelix_dir, t.id, agent_id)

        allowed = _wave_allowed_task_ids(tasks)
        attempted: set[str] = set()
        while True:
            candidates = [
                t for t in tasks if t.id not in attempted and t.id in allowed
            ]
            task = select_next(candidates, autonomy=cfg.autonomy.level)
            if task is None:
                return None
            attempted.add(task.id)
            if claim_task(
                cfg.kelix_dir,
                task.id,
                agent_id,
                branch="",
                stale_after_s=spec.stale_claim_s,
            ):
                return (
                    f"Your assigned task for this iteration: {task.id} — "
                    f"{task.title}. Work ONLY this task."
                )
            # Claimed by someone else: try the next candidate.

    return hook


def fleet_id_from_config(config_file: str) -> str:
    """Stable fleet identifier from the fleet config path (e.g. ``fleet.toml`` -> ``fleet``)."""
    return Path(config_file).stem


def compute_fleet_summary(fleet_id: str, results: dict[str, RunResult]) -> FleetSummaryRow:
    """Aggregate per-agent run results into one fleet-level summary row."""
    run_ids: list[str] = []
    verified = 0
    iteration_count = 0
    breaker_trips = 0

    for result in results.values():
        if result.run_id:
            run_ids.append(result.run_id)
        if result.status == "circuit_breaker":
            breaker_trips += 1
        if result.ledger_rows:
            iteration_count += len(result.ledger_rows)
            verified += sum(1 for row in result.ledger_rows if row.verified)
        else:
            iteration_count += len(result.iterations)
            verified += sum(1 for rec in result.iterations if rec.verified)

    verified_rate = verified / iteration_count if iteration_count else 0.0
    return FleetSummaryRow(
        fleet_id=fleet_id,
        run_ids=run_ids,
        verified_rate=verified_rate,
        iteration_count=iteration_count,
        breaker_trips=breaker_trips,
    )


def run_fleet(cfg: Config, config_file: str, max_iterations: int | None = None) -> int:
    spec = load_fleet_spec(cfg, config_file)
    fleet_id = fleet_id_from_config(config_file)
    cap = max_iterations or spec.max_iterations
    results: dict[str, RunResult] = {}
    errors: dict[str, str] = {}

    def worker(agent: FleetAgent):
        runner = Runner(
            cfg,
            role=spec.role_prompt(agent.role),
            agent_id=agent.id,
            fleet_id=fleet_id,
            pre_iteration=make_claim_hook(cfg, spec, agent.id),
        )
        try:
            results[agent.id] = runner.run(
                max_iterations=cap, log=lambda msg: print(f"[{agent.id}] {msg}")
            )
        except Exception as exc:  # one agent's crash must not kill the fleet
            errors[agent.id] = str(exc)

    threads = [
        threading.Thread(target=worker, args=(agent,), name=agent.id)
        for agent in spec.agents
    ]
    for i, t in enumerate(threads):
        t.start()
        # Stagger starts: run ids are timestamped per second, and worktree
        # creation from the same HEAD is cheap but not free.
        if i < len(threads) - 1:
            time.sleep(1.1)
    for t in threads:
        t.join()

    _write_fleet_retrospective(cfg, spec, results, errors)
    if results:
        try:
            summary = compute_fleet_summary(fleet_id, results)
            append_run_metrics(cfg, [], fleet_summary=summary)
        except Exception as exc:  # metrics rollup must never mask fleet status
            print(f"fleet metrics rollup failed: {exc}")
    failed = bool(errors) or any(
        r.status not in ("completed", "max_iterations") for r in results.values()
    )
    return 1 if failed else 0


def infer_task_kind(task: Task) -> str:
    """Heuristic task kind from title and phase (test/docs/fix/feature)."""
    text = f"{task.title} {task.phase}".strip()
    for kind, pattern in _TASK_KIND_PATTERNS:
        if pattern.search(text):
            return kind
    return "feature"


def _task_id_from_rationale(rationale: str) -> str:
    if not rationale:
        return ""
    text = rationale.strip()
    if text.startswith(FROM_COMMIT_RATIONALE_PREFIX):
        text = text[len(FROM_COMMIT_RATIONALE_PREFIX) :].strip()
    match = TASK_FROM_RATIONALE_RE.match(text)
    return match.group(1).rstrip("—") if match else ""


def _role_match_label(role: str, task: Task | None) -> str:
    if task is None:
        return ""
    kind = infer_task_kind(task)
    preferred = ROLE_PREFERRED_KINDS.get(role)
    if preferred is None:
        return f"; role-match: n/a ({role} vs {kind})"
    matched = kind in preferred
    verdict = "yes" if matched else "no"
    return f"; role-match: {verdict} ({role} vs {kind})"


def _count_role_drift(
    role: str, iterations: list[IterationRecord], tasks_by_id: dict[str, Task]
) -> tuple[int, int]:
    """Return (drift_count, scored_iterations) for a built-in role."""
    preferred = ROLE_PREFERRED_KINDS.get(role)
    if preferred is None:
        return 0, 0
    drift = 0
    scored = 0
    for rec in iterations:
        task_id = _task_id_from_rationale(rec.rationale)
        if not task_id:
            continue
        task = tasks_by_id.get(task_id)
        if task is None:
            continue
        scored += 1
        if infer_task_kind(task) not in preferred:
            drift += 1
    return drift, scored


def _write_fleet_retrospective(
    cfg: Config,
    spec: FleetSpec,
    results: dict[str, RunResult],
    errors: dict[str, str],
) -> None:
    out_dir = cfg.kelix_dir / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"fleet-{time.strftime('%Y%m%d-%H%M%S')}.md"
    backlog_path = cfg.root / cfg.loop.plan_file
    tasks_by_id: dict[str, Task] = {}
    if backlog_path.is_file():
        tasks_by_id = {
            task.id: task
            for task in parse_backlog(backlog_path.read_text(encoding="utf-8"))
        }

    lines = ["# Fleet retrospective", ""]
    for agent in spec.agents:
        lines.append(f"## {agent.id} ({agent.role})")
        r = results.get(agent.id)
        if r is None:
            lines.append(f"- crashed before producing a result: {errors.get(agent.id)}")
            lines.append("")
            continue
        lines.append(f"- status: {r.status}; branch: `{r.branch}`")
        for rec in r.iterations:
            outcome = f"FAIL ({rec.failure})" if rec.failure else (
                "verified" if rec.verified else "ok"
            )
            task_id = _task_id_from_rationale(rec.rationale)
            task = tasks_by_id.get(task_id) if task_id else None
            role_match = _role_match_label(agent.role, task)
            lines.append(
                f"  - iter {rec.index}: {rec.rationale or '(none)'} -> {outcome}"
                f"{role_match}"
            )
        drift, scored = _count_role_drift(agent.role, r.iterations, tasks_by_id)
        if scored:
            lines.append(f"- role drift: {drift}/{scored} iterations")
        lines.append("")
    lines.append("## Task claims at end of fleet run")
    for claim in list_claims(cfg.kelix_dir):
        done = " (done)" if claim.get("done") else ""
        lines.append(f"- {claim['task']}: {claim['agent']}{done}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"fleet retrospective: {path}")


def _tasks_for_req(req_id: str, tasks: list[Task]) -> list[Task]:
    return [
        task
        for task in tasks
        if req_id in [part.strip() for part in task.req.split(",") if part.strip()]
    ]


def _covering_task_id(tasks_for_req: list[Task]) -> str:
    done = [task for task in tasks_for_req if task.status == "done"]
    if done:
        return done[0].id
    if tasks_for_req:
        return tasks_for_req[0].id
    return "-"


def _pending_task_wave_lines(cfg: Config) -> list[str]:
    backlog_path = cfg.root / cfg.loop.plan_file
    if not backlog_path.is_file():
        return []

    tasks = parse_backlog(backlog_path.read_text(encoding="utf-8"))
    pending = [task for task in tasks if task.status != "done"]
    if not pending:
        return []

    wave_list, has_cycle = waves(tasks)
    wave_by_id = {
        task.id: index for index, wave in enumerate(wave_list) for task in wave
    }

    lines = ["", "Pending tasks (waves):"]
    for task in sorted(
        pending,
        key=lambda item: (wave_by_id.get(item.id, 999), -item.priority, item.id),
    ):
        wave_num = wave_by_id.get(task.id, "?")
        lines.append(f"  wave {wave_num}: {task.id} ({task.status})")
    if has_cycle:
        lines.append("  warning: dependency cycle detected")
    return lines


def _phase_gate_status_lines(cfg: Config) -> list[str]:
    roadmap = load_roadmap(cfg.kelix_dir)
    if roadmap is None:
        return []

    state = load_state(cfg.kelix_dir)
    if state is None or not state.phase:
        return []

    phase = next((p for p in roadmap.phases if p.id == state.phase), None)
    phase_label = f"{state.phase} — {phase.title}" if phase else state.phase

    lines = [""]
    if state.milestone:
        lines.append(f"Milestone: {state.milestone}")
    lines.append(f"Phase: {phase_label}")

    backlog_path = cfg.root / cfg.loop.plan_file
    tasks: list[Task] = []
    if backlog_path.is_file():
        tasks = parse_backlog(backlog_path.read_text(encoding="utf-8"))

    entries = coverage(roadmap, tasks, state.phase)
    req_entries = [entry for entry in entries if entry.status != "warning"]
    if req_entries:
        lines.append("")
        lines.append("Phase gate coverage:")
        lines.append(f"  {'REQ-ID':<10} {'status':<12} task")
        for entry in req_entries:
            task_id = _covering_task_id(_tasks_for_req(entry.req_id, tasks))
            lines.append(f"  {entry.req_id:<10} {entry.status:<12} {task_id}")

    warnings = [entry for entry in entries if entry.status == "warning"]
    for entry in warnings:
        lines.append(f"  warning: {entry.message}")

    if state.blockers:
        lines.append("")
        lines.append("Blockers:")
        for blocker in state.blockers:
            lines.append(f"  - {blocker}")

    return lines


def render_status(cfg: Config) -> str:
    """Live view assembled purely from coordination files + git."""
    lines = ["kelix status", "============"]
    lines.extend(_phase_gate_status_lines(cfg))
    lines.extend(_pending_task_wave_lines(cfg))
    stop = cfg.kelix_dir / "STOP"
    if stop.exists():
        lines.append("KILL SWITCH SET (.kelix/STOP) — runs will halt")

    claims = list_claims(cfg.kelix_dir)
    if claims:
        lines.append("\nTask claims:")
        for c in claims:
            age = int(time.time() - c.get("heartbeat", c.get("ts", 0)))
            state = "done" if c.get("done") else f"active, heartbeat {age}s ago"
            lines.append(f"  {c['task']:<12} {c.get('agent', '?'):<14} {state}")
    else:
        lines.append("\nNo task claims (no fleet activity).")

    runs_dir = cfg.kelix_dir / "runs"
    if runs_dir.is_dir():
        runs = sorted(d for d in runs_dir.iterdir() if d.is_dir())[-5:]
        if runs:
            lines.append("\nRecent runs:")
            for run in runs:
                status = "?"
                run_json = run / "run.json"
                if run_json.is_file():
                    import json

                    try:
                        data = json.loads(run_json.read_text(encoding="utf-8"))
                        status = f"{data.get('status')} ({len(data.get('iterations', []))} iters)"
                        branch = data.get("branch", "")
                        if branch:
                            last = git(
                                ["log", "-1", "--format=%h %s", branch],
                                cfg.root,
                                check=False,
                            ).strip()
                            status += f" | {branch} @ {last}"
                    except (json.JSONDecodeError, OSError):
                        pass
                lines.append(f"  {run.name}: {status}")

    mailbox = cfg.kelix_dir / "fleet" / "mailbox"
    if mailbox.is_dir():
        notes = sorted(mailbox.glob("*.md"))
        if notes:
            lines.append(f"\nMailbox: {len(notes)} note(s), latest: {notes[-1].name}")
    return "\n".join(lines)
