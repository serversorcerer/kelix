"""Fleet mode: N independent Kalph loops, one repo, coordination through files.

No message bus, no RPC (mission non-goal). Coordination surface:
- `.kalph/fleet/claims/<task>.json` — atomic task claims (claims.py)
- `.kalph/fleet/mailbox/*.md`       — notes between agents, read at iteration start
- `.kalph/fleet/skills/`            — shared skill discoveries
Everything `kalph status` shows is derived from these files plus git.
"""

from __future__ import annotations

import threading
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .backlog import parse_backlog, select_next
from .claims import claim_task, list_claims, mark_claim_done
from .config import Config
from .gitutil import git
from .loop import Runner, RunResult

BUILTIN_ROLES: dict[str, str] = {
    "builder": (
        "Role: builder. Prefer feature and implementation tasks. Do not take "
        "tasks that are purely tests, docs, or fixing other agents' breakage "
        "unless nothing else is eligible."
    ),
    "verifier": (
        "Role: verifier. Prefer tasks that write or strengthen tests. Also: "
        "each iteration, look at open kalph/* branches or PRs (`git branch -a`, "
        "`gh pr list` if available); if you find problems in another agent's "
        "work, leave a review note as a new file in .kalph/fleet/mailbox/ "
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
    "You are one agent in a Kalph fleet. Coordination rules: work ONLY the "
    "task assigned below (it is claimed for you; other tasks may be claimed "
    "by other agents). If your work affects others (schema changes, renamed "
    "modules, API changes), leave a note file in .kalph/fleet/mailbox/ named "
    "<timestamp>-<your-role>.md. If you write a new skill, also copy it to "
    ".kalph/fleet/skills/<name>/SKILL.md so other agents see it immediately."
)


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
            c["task"] for c in list_claims(cfg.kalph_dir) if c.get("done")
        }
        for t in tasks:
            if t.id in done_elsewhere and t.status != "done":
                t.status = "done"

        # Release-on-done: mark our own completed tasks in the shared claims.
        for t in tasks:
            if t.status == "done":
                mark_claim_done(cfg.kalph_dir, t.id, agent_id)

        attempted: set[str] = set()
        while True:
            candidates = [t for t in tasks if t.id not in attempted]
            task = select_next(candidates, autonomy=cfg.autonomy.level)
            if task is None:
                return None
            attempted.add(task.id)
            if claim_task(
                cfg.kalph_dir,
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


def run_fleet(cfg: Config, config_file: str, max_iterations: int | None = None) -> int:
    spec = load_fleet_spec(cfg, config_file)
    cap = max_iterations or spec.max_iterations
    results: dict[str, RunResult] = {}
    errors: dict[str, str] = {}

    def worker(agent: FleetAgent):
        runner = Runner(
            cfg,
            role=spec.role_prompt(agent.role),
            agent_id=agent.id,
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
    failed = bool(errors) or any(
        r.status not in ("completed", "max_iterations") for r in results.values()
    )
    return 1 if failed else 0


def _write_fleet_retrospective(
    cfg: Config,
    spec: FleetSpec,
    results: dict[str, RunResult],
    errors: dict[str, str],
) -> None:
    out_dir = cfg.kalph_dir / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"fleet-{time.strftime('%Y%m%d-%H%M%S')}.md"
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
            lines.append(f"  - iter {rec.index}: {rec.rationale or '(none)'} -> {outcome}")
        lines.append("")
    lines.append("## Task claims at end of fleet run")
    for claim in list_claims(cfg.kalph_dir):
        done = " (done)" if claim.get("done") else ""
        lines.append(f"- {claim['task']}: {claim['agent']}{done}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"fleet retrospective: {path}")


def render_status(cfg: Config) -> str:
    """Live view assembled purely from coordination files + git."""
    lines = ["kalph status", "============"]
    stop = cfg.kalph_dir / "STOP"
    if stop.exists():
        lines.append("KILL SWITCH SET (.kalph/STOP) — runs will halt")

    claims = list_claims(cfg.kalph_dir)
    if claims:
        lines.append("\nTask claims:")
        for c in claims:
            age = int(time.time() - c.get("heartbeat", c.get("ts", 0)))
            state = "done" if c.get("done") else f"active, heartbeat {age}s ago"
            lines.append(f"  {c['task']:<12} {c.get('agent', '?'):<14} {state}")
    else:
        lines.append("\nNo task claims (no fleet activity).")

    runs_dir = cfg.kalph_dir / "runs"
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

    mailbox = cfg.kalph_dir / "fleet" / "mailbox"
    if mailbox.is_dir():
        notes = sorted(mailbox.glob("*.md"))
        if notes:
            lines.append(f"\nMailbox: {len(notes)} note(s), latest: {notes[-1].name}")
    return "\n".join(lines)
