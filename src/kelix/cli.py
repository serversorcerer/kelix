"""Kelix command-line interface — run any headless coding agent in a verified loop."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .config import ConfigError, load_config

INIT_AGENTS = ("kiro", "claude", "codex", "cursor", "gemini", "cmd", "mock")

BACKLOG_TEMPLATE = """\
# Kelix backlog

Loop contract: one task per iteration, highest-priority `ready` task whose
dependencies are done. Owner tasks outrank `proposed` tasks. Done means
verified-done. See docs for the task format.

## Tasks

- [ ] T1: (describe the first task) | priority: 50 | status: ready | by: owner
  rationale: (why this matters)
"""

PROJECT_MEMORY_TEMPLATE = """\
# Project memory

Durable facts about this repo that future iterations should know:
architecture notes, conventions, build/test quirks, gotchas. Keep entries
short; this file is injected into agent context by reference.
"""

CLI_DESCRIPTION = (
    "Run headless coding agents — Claude Code, Codex CLI, Cursor, Gemini CLI, "
    "Kiro, or your own CLI adapter — in a verified loop. All state lives in "
    "files and git; every iteration is a fresh agent, one task, verified-done."
)

def render_config_template(adapter: str = "kiro") -> str:
    if adapter not in INIT_AGENTS:
        raise ValueError(f"unknown adapter {adapter!r}")
    cmd_line = ""
    if adapter == "cmd":
        cmd_line = 'command = "your-cli {prompt}"  # required when adapter = cmd\n'
    return f"""\
# Kelix configuration. Every field is optional; defaults are safe.

[agent]
adapter = "{adapter}"          # kiro | claude | codex | cursor | gemini | cmd | mock
{cmd_line}\
[loop]
max_iterations = 25
circuit_breaker_threshold = 3
# diagnose_transcript_chars = 50000   # kelix diagnose transcript budget
# diagnose_default_runs = 3             # kelix diagnose --last N default

[verify]
# Commands that define "done". All must exit 0.
commands = []

[git]
isolation = "worktree"    # worktree | branch | none

# [memory]
# distill_skills = true     # post-retrospective skill distillation pass
"""


CONFIG_TEMPLATE = render_config_template("kiro")


def resolve_init_agent(
    args,
    *,
    is_tty: bool | None = None,
    input_fn=input,
    print_fn=print,
) -> str | None:
    """Return adapter name for a new kelix.toml, or None when init should abort."""
    chosen = getattr(args, "agent", "") or ""
    if chosen:
        if chosen not in INIT_AGENTS:
            print(f"error: unknown agent {chosen!r}", file=sys.stderr)
            return None
        return chosen
    if is_tty is None:
        is_tty = sys.stdin.isatty()
    if not is_tty:
        print(
            "error: non-interactive init requires --agent "
            f"<{'|'.join(INIT_AGENTS)}>",
            file=sys.stderr,
        )
        return None
    print_fn("Choose your default coding agent:")
    for index, name in enumerate(INIT_AGENTS, start=1):
        print_fn(f"  {index}) {name}")
    default = INIT_AGENTS[0]
    while True:
        raw = input_fn(f"Agent [1={default}]: ").strip()
        if not raw:
            return default
        if raw.isdigit():
            choice = int(raw)
            if 1 <= choice <= len(INIT_AGENTS):
                return INIT_AGENTS[choice - 1]
        if raw in INIT_AGENTS:
            return raw
        print_fn(f"Enter 1–{len(INIT_AGENTS)} or an agent name.")

PHASES_README_TEMPLATE = """\
# Phase decision files

Each phase may have a `CONTEXT.md` in `.kelix/phases/<phase-id>/CONTEXT.md`
holding owner decisions made during planning (the GSD Discuss artifact). When
STATE.md names an active phase and that file exists, its contents are injected
into the iteration prompt as read-only data — not instructions.
"""

GOAL_TEMPLATE = """\
# Project goal

Describe what should exist when this work ships, and for whom.

## Non-goals

What the loop must NOT build, even if tempting.

## Acceptance

- Each bullet is testable — it becomes verify evidence or a backlog task's
  acceptance signal.
- (add acceptance criteria here)
"""

ROADMAP_TEMPLATE = """\
# Kelix roadmap

<!-- Optional. Delete this file to use a flat backlog (no milestones or phase
gates). See docs/planning.md for the plan-first flow. -->

## Milestone M1 — (release title)

Describe what exists when this milestone ships, and for whom.

Non-goals: what the loop must NOT build, even if tempting.

### Phase P-EXAMPLE — (phase title)

Outcome: one sentence — what "done" means for this phase.

- REQ-EX1: (testable requirement — every REQ must map to backlog task(s))
- REQ-EX2: (another requirement)

### Phase P-NEXT — (next phase title)

Outcome: (next phase outcome)

- REQ-N1: (requirement for the next phase)
"""


def cmd_init(
    args,
    *,
    is_tty: bool | None = None,
    input_fn=input,
    print_fn=print,
) -> int:
    root = Path(args.path).resolve()
    kelix = root / ".kelix"
    kelix_toml = kelix / "kelix.toml"
    kelix_toml_content = CONFIG_TEMPLATE
    if not kelix_toml.exists():
        agent = resolve_init_agent(
            args,
            is_tty=is_tty,
            input_fn=input_fn,
            print_fn=print_fn,
        )
        if agent is None:
            return 2
        kelix_toml_content = render_config_template(agent)
    created = []
    for rel, content in [
        ("backlog.md", BACKLOG_TEMPLATE),
        ("memory/project.md", PROJECT_MEMORY_TEMPLATE),
        ("kelix.toml", kelix_toml_content),
    ]:
        path = kelix / rel
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            created.append(str(path.relative_to(root)))
    (kelix / "skills").mkdir(exist_ok=True)
    (kelix / "prompts").mkdir(exist_ok=True)
    phases_readme = kelix / "phases" / "README.md"
    if not phases_readme.exists():
        phases_readme.parent.mkdir(parents=True, exist_ok=True)
        phases_readme.write_text(PHASES_README_TEMPLATE, encoding="utf-8")
        created.append(str(phases_readme.relative_to(root)))
    goal_path = root / "GOAL.md"
    if not goal_path.exists():
        goal_path.write_text(GOAL_TEMPLATE, encoding="utf-8")
        created.append("GOAL.md")
    roadmap_path = kelix / "roadmap.md"
    if not roadmap_path.exists():
        roadmap_path.write_text(ROADMAP_TEMPLATE, encoding="utf-8")
        created.append(str(roadmap_path.relative_to(root)))
    from .art import banner, next_steps, say

    if args.from_spec:
        from .kiro import import_spec

        count = import_spec(root, args.from_spec)
        print(
            say(
                f"imported {count} tasks from .kiro/specs/{args.from_spec}/tasks.md",
                "ok",
            )
        )

    print(banner())
    if created:
        print(say("initialized: " + ", ".join(created), "ok"))
    else:
        print(say("already initialized — nothing overwritten", "info"))
    print(
        next_steps(
            [
                "describe your goal in GOAL.md",
                "kelix plan --goal-file GOAL.md   (it will interview you)",
                "review the draft, promote tasks to ready",
                "kelix run                        (wake up to verified commits)",
            ]
        )
    )
    return 0


def cmd_lint(args) -> int:
    from .art import say
    from .lint import format_finding, lint_repo

    root = Path(args.path).resolve()
    findings = lint_repo(root)
    if not findings:
        print(say("lint: clean — good input in, good output out", "ok"))
        return 0
    for finding in findings:
        print(say(f"lint: {format_finding(finding)}", "warn"), file=sys.stderr)
    print(say(f"{len(findings)} finding(s) — slop in, slop out", "fail"), file=sys.stderr)
    return 1


def cmd_plan(args) -> int:
    from .loop import LoopError
    from .plan import PlanRunner

    root = Path(args.path).resolve()
    if args.goal_file:
        goal_path = Path(args.goal_file)
        if not goal_path.is_file():
            print(f"error: goal file not found: {goal_path}", file=sys.stderr)
            return 2
        goal = goal_path.read_text(encoding="utf-8")
    else:
        goal = args.goal or ""

    try:
        cfg = load_config(root)
        result = PlanRunner(cfg).run(goal=goal)
    except (ConfigError, LoopError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    from .art import say

    if result.status == "completed":
        print(
            say(
                "draft plan ready — review .kelix/roadmap.md and promote "
                "tasks to ready",
                "ok",
            )
        )
        return 0

    if result.status == "awaiting_answers":
        if result.questions_path:
            print(
                say(
                    f"planning questions written — answer them in "
                    f"{result.questions_path}, then re-run kelix plan with "
                    "the same goal",
                    "climb",
                )
            )
        return 0

    if result.findings:
        for line in result.findings:
            print(f"lint: {line}", file=sys.stderr)  # pre-formatted in plan.py
    if result.iteration and result.iteration.failure:
        print(f"error: {result.iteration.failure}", file=sys.stderr)
    return 1


def cmd_run(args) -> int:
    from .loop import LoopError, Runner

    if sys.stdout.isatty():
        from .art import banner

        print(banner())
    try:
        cfg = load_config(Path(args.path))
        runner = Runner(cfg, role=args.role or "")
        result = runner.run(max_iterations=args.max_iterations)
    except (ConfigError, LoopError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.pr and result.status in ("completed", "max_iterations"):
        from .art import say
        from .pr import open_pr

        run_dir = cfg.kelix_dir / "runs" / result.run_id
        pr_url = open_pr(cfg, result, run_dir)
        if pr_url:
            print(say(f"PR opened: {pr_url}", "ok"))
    return 0 if result.status in ("completed", "max_iterations") else 1


def cmd_watch(args) -> int:
    from .art import say, strip
    from .watch import find_active_runs, follow

    cfg = load_config(Path(args.path))
    runs_dir = cfg.kelix_dir / "runs"

    run_id = args.run_id
    if not run_id:
        active = find_active_runs(runs_dir)
        if not active:
            print(
                say(
                    "no active run — start one with `kelix run`, "
                    "then watch it work",
                    "info",
                )
            )
            return 1
        if len(active) > 1:
            print(say(f"{len(active)} active runs (watching newest):", "info"))
            for hb in active:
                print(f"    {hb.run_id}  role={hb.role or '-'}  iter {hb.iteration}")
            print(say("pick one with --run-id", "info"))
        run_id = active[0].run_id

    if sys.stdout.isatty():
        print(strip())
    print(say(f"watching run {run_id} — ctrl-c detaches, the loop keeps going", "climb"))

    def emit(text: str) -> None:
        print(text, end="", flush=True)

    try:
        code = follow(runs_dir, run_id, emit)
    except KeyboardInterrupt:
        print()
        print(say(f"detached — run {run_id} continues unattended", "ok"))
        return 0
    if code != 0:
        print(say(f"no heartbeat for run {run_id} (too old, or never started)", "warn"))
    return code


def cmd_status(args) -> int:
    from .art import say, strip
    from .fleet import render_status

    cfg = load_config(Path(args.path))
    if sys.stdout.isatty():
        print(strip())
    print(say("kelix status — assembled from coordination files", "info"))
    for line in render_status(cfg).splitlines():
        if line in ("kelix status", "============"):
            continue
        if "KILL SWITCH" in line:
            print(say(line, "warn"))
        elif line.startswith("Live now"):
            print(say(line, "climb"))
        elif line.startswith("No task claims"):
            print(say(line, "info"))
        else:
            print(line)
    return 0


def cmd_stop(args) -> int:
    cfg = load_config(Path(args.path))
    stop = cfg.kelix_dir / "STOP"
    stop.parent.mkdir(parents=True, exist_ok=True)
    stop.write_text("stop requested by owner\n", encoding="utf-8")
    from .art import say

    print(
        say(
            f"kill switch set: {stop} — runs halt before next iteration; "
            "remove the file to resume",
            "warn",
        )
    )
    return 0


def cmd_fleet(args) -> int:
    from .fleet import run_fleet

    cfg = load_config(Path(args.path))
    return run_fleet(cfg, config_file=args.config, max_iterations=args.max_iterations)


def cmd_mcp(args) -> int:
    from .mcp_server import serve

    serve(Path(args.path))
    return 0


def cmd_diagnose(args) -> int:
    from .config import ConfigError
    from .diagnose import DiagnoseError, DiagnoseRunner
    from .loop import LoopError

    root = Path(args.path).resolve()
    try:
        cfg = load_config(root)
        result = DiagnoseRunner(cfg).run(
            run_ids=args.run_id or None,
            last_n=args.last,
            diagnosis_file=args.diagnosis_file or "",
        )
    except (ConfigError, DiagnoseError, LoopError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    from .art import say

    if result.status == "completed":
        print(say(f"diagnosis written: {result.diagnosis_path}", "ok"))
        return 0

    for finding in result.findings:
        print(f"error: {finding}", file=sys.stderr)
    return 1 if result.status == "validation_failed" else 2


def cmd_propose(args) -> int:
    from .config import ConfigError
    from .loop import LoopError
    from .propose import ProposeError, ProposeRunner, metrics_excerpt

    root = Path(args.path).resolve()
    try:
        cfg = load_config(root)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if getattr(args, "record_merge", None):
        return _cmd_record_proposal(
            cfg,
            merge_sha=args.record_merge,
            close_reason="",
            proposal_id=args.proposal_id or "",
            merged_at_run=args.merged_at_run or "",
        )
    if getattr(args, "record_close", None):
        return _cmd_record_proposal(
            cfg,
            merge_sha="",
            close_reason=args.record_close,
            proposal_id=args.proposal_id or "",
            merged_at_run="",
        )

    try:
        result = ProposeRunner(cfg).run(
            diagnosis_file=args.diagnosis_file or "",
        )
    except (ProposeError, LoopError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    from .art import say

    if result.status == "completed":
        print(say(f"proposal ready: branch {result.branch}", "ok"))
        print(say(f"sidecar written: {result.sidecar_path}", "ok"))
        if result.iteration and result.iteration.predicted_improvement:
            print(f"predicted improvement: {result.iteration.predicted_improvement}")
        if not getattr(args, "no_pr", False):
            from .pr import open_propose_pr

            pr_url = open_propose_pr(
                cfg,
                result,
                metrics_excerpt=metrics_excerpt(cfg),
                diagnosis_file=result.diagnosis_file,
            )
            if pr_url:
                print(say(f"PR opened: {pr_url}", "ok"))
        return 0

    for finding in result.findings:
        print(f"error: {finding}", file=sys.stderr)
    return 1 if result.status == "validation_failed" else 2


def _cmd_record_proposal(
    cfg,
    *,
    merge_sha: str,
    close_reason: str,
    proposal_id: str,
    merged_at_run: str,
) -> int:
    from .metrics import (
        default_merged_at_run_id,
        load_metrics,
        metrics_path,
        record_proposal_outcome,
        save_metrics,
    )
    from .propose import ProposeError, latest_proposal_id, load_proposal_sidecar

    pid = proposal_id or latest_proposal_id(cfg)
    if not pid:
        print("error: no proposal_id and no proposal sidecar found", file=sys.stderr)
        return 2

    try:
        sidecar = load_proposal_sidecar(cfg, pid)
    except ProposeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    path = metrics_path(cfg)
    metrics = load_metrics(path)
    run_boundary = merged_at_run or default_merged_at_run_id(metrics)
    prediction = str(sidecar.get("prediction") or "")

    try:
        outcome = record_proposal_outcome(
            metrics,
            proposal_id=pid,
            prediction=prediction,
            merge_sha=merge_sha,
            close_reason=close_reason,
            merged_at_run_id=run_boundary,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    save_metrics(path, metrics)
    from .art import say

    label = merge_sha or close_reason
    print(say(f"recorded proposal {pid}: {label}", "ok"))
    print(f"grade: {outcome.grade or 'pending'}")
    return 0


def cmd_metrics_grade_proposal(args) -> int:
    from .config import ConfigError
    from .metrics import grade_proposal, load_metrics, metrics_path, save_metrics

    root = Path(args.path).resolve()
    try:
        cfg = load_config(root)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    path = metrics_path(cfg)
    metrics = load_metrics(path)
    try:
        grade = grade_proposal(metrics, args.proposal_id)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    save_metrics(path, metrics)
    from .art import say

    print(say(f"proposal {args.proposal_id}: {grade}", "ok"))
    return 0


def cmd_sync(args) -> int:
    """Mirror tracker issues into the backlog. Non-fatal: tracker problems are
    logged and skipped, never fatal to the loop."""
    from .sync import make_tracker
    from .sync.mirror import mirror_inbound

    cfg = load_config(Path(args.path))
    tracker = make_tracker(cfg)
    if tracker is None:
        print("tracker sync disabled ([tracker].provider unset in kelix.toml)")
        return 0
    issues = tracker.fetch_issues()
    added = mirror_inbound(cfg.root / cfg.loop.plan_file, issues)
    print(f"synced {len(issues)} issue(s) from {tracker.name}; {added} new backlog task(s)")
    return 0


def main(argv: list[str] | None = None) -> int:
    from .art import banner

    description = CLI_DESCRIPTION
    if sys.stdout.isatty():
        description = f"{CLI_DESCRIPTION}\n\n{banner()}"
    parser = argparse.ArgumentParser(
        prog="kelix",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=description,
        epilog=(
            "the flow: kelix init -> kelix plan (it interviews you) -> "
            "review -> kelix run\n"
            "every iteration: fresh agent, one task, verified-done, committed."
        ),
    )
    parser.add_argument("--version", action="version", version=f"kelix {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="initialize .kelix/ in a repository")
    p.add_argument("--path", default=".")
    p.add_argument(
        "--agent",
        choices=INIT_AGENTS,
        default="",
        help=(
            "default coding agent adapter written to kelix.toml "
            "(required when stdin is not a TTY)"
        ),
    )
    p.add_argument("--from-spec", default="", help="seed backlog from .kiro/specs/<name>/tasks.md")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("lint", help="check backlog tasks against the input contract")
    p.add_argument("--path", default=".")
    p.set_defaults(func=cmd_lint)

    p = sub.add_parser("plan", help="draft roadmap and backlog from a goal")
    p.add_argument("--path", default=".")
    p.add_argument("goal", nargs="?", default="", help="goal text")
    p.add_argument(
        "--goal-file",
        default="",
        help="read goal from a file (e.g. GOAL.md)",
    )
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser(
        "run",
        help="run the verified loop with the configured coding agent",
    )
    p.add_argument("--path", default=".")
    p.add_argument("--max-iterations", type=int, default=None)
    p.add_argument("--role", default="", help="role text to inject into the prompt")
    p.add_argument(
        "--pr",
        action="store_true",
        help="open a GitHub PR after a completed or max-iterations run",
    )
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("status", help="show run/fleet status from coordination files")
    p.add_argument("--path", default=".")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("watch", help="stream a running loop's agent output live")
    p.add_argument("--path", default=".")
    p.add_argument("--run-id", default="", help="watch a specific run (default: newest active)")
    p.set_defaults(func=cmd_watch)

    p = sub.add_parser("stop", help="set the kill switch (.kelix/STOP)")
    p.add_argument("--path", default=".")
    p.set_defaults(func=cmd_stop)

    p = sub.add_parser("fleet", help="run a coordinated fleet of loops")
    p.add_argument("--path", default=".")
    p.add_argument("--config", default=".kelix/fleet.toml")
    p.add_argument("--max-iterations", type=int, default=None)
    p.set_defaults(func=cmd_fleet)

    p = sub.add_parser(
        "mcp",
        help="serve Kelix as an MCP server for MCP-capable agents (stdio)",
    )
    p.add_argument("--path", default=".")
    p.set_defaults(func=cmd_mcp)

    p = sub.add_parser("sync", help="mirror tracker issues into the backlog")
    p.add_argument("--path", default=".")
    p.set_defaults(func=cmd_sync)

    p = sub.add_parser(
        "diagnose",
        help="review failed runs and write a diagnosis (owner-invoked)",
    )
    p.add_argument("--path", default=".")
    p.add_argument(
        "--run-id",
        action="append",
        default=[],
        dest="run_id",
        help="run id to include (repeatable; overrides --last)",
    )
    p.add_argument(
        "--last",
        type=int,
        default=None,
        help="most recent N runs with failures (default: loop.diagnose_default_runs)",
    )
    p.add_argument(
        "--diagnosis-file",
        default="",
        help="output path (default: .kelix/memory/diagnosis-<timestamp>.md)",
    )
    p.set_defaults(func=cmd_diagnose)

    p = sub.add_parser(
        "propose",
        help="propose a policy-surface tuning change (owner-invoked)",
    )
    p.add_argument("--path", default=".")
    p.add_argument(
        "--diagnosis-file",
        default="",
        help="optional diagnosis markdown to include as evidence",
    )
    p.add_argument(
        "--no-pr",
        action="store_true",
        help="skip opening a GitHub PR after a successful proposal",
    )
    p.add_argument(
        "--record-merge",
        metavar="SHA",
        default="",
        help="record a merged proposal outcome (skips adapter iteration)",
    )
    p.add_argument(
        "--record-close",
        metavar="REASON",
        default="",
        help="record a closed proposal outcome without merge",
    )
    p.add_argument(
        "--proposal-id",
        default="",
        help="proposal id for --record-merge/--record-close (default: latest sidecar)",
    )
    p.add_argument(
        "--merged-at-run",
        default="",
        help="last pre-merge run id for grading window (default: last ledger run)",
    )
    p.set_defaults(func=cmd_propose)

    metrics_p = sub.add_parser("metrics", help="inspect or update loop outcome ledger")
    metrics_sub = metrics_p.add_subparsers(dest="metrics_command", required=True)
    grade_p = metrics_sub.add_parser(
        "grade-proposal",
        help="re-grade a recorded proposal from loop-metrics.json windows",
    )
    grade_p.add_argument("--path", default=".")
    grade_p.add_argument(
        "--proposal-id",
        required=True,
        help="proposal id to grade",
    )
    grade_p.set_defaults(func=cmd_metrics_grade_proposal)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
