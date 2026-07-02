"""Kelix command-line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .config import ConfigError, load_config

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

CONFIG_TEMPLATE = """\
# Kelix configuration. Every field is optional; defaults are safe.

[agent]
adapter = "kiro"          # kiro | cmd | mock

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
"""

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


def cmd_init(args) -> int:
    root = Path(args.path).resolve()
    kelix = root / ".kelix"
    created = []
    for rel, content in [
        ("backlog.md", BACKLOG_TEMPLATE),
        ("memory/project.md", PROJECT_MEMORY_TEMPLATE),
        ("kelix.toml", CONFIG_TEMPLATE),
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
    if args.from_spec:
        from .kiro import import_spec

        count = import_spec(root, args.from_spec)
        print(f"imported {count} tasks from .kiro/specs/{args.from_spec}/tasks.md")
    from .art import banner, next_steps, say

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
        from .pr import open_pr

        run_dir = cfg.kelix_dir / "runs" / result.run_id
        pr_url = open_pr(cfg, result, run_dir)
        if pr_url:
            print(f"PR opened: {pr_url}")
    return 0 if result.status in ("completed", "max_iterations") else 1


def cmd_status(args) -> int:
    from .art import strip
    from .fleet import render_status

    cfg = load_config(Path(args.path))
    if sys.stdout.isatty():
        print(strip())
    print(render_status(cfg))
    return 0


def cmd_stop(args) -> int:
    cfg = load_config(Path(args.path))
    stop = cfg.kelix_dir / "STOP"
    stop.parent.mkdir(parents=True, exist_ok=True)
    stop.write_text("stop requested by owner\n", encoding="utf-8")
    print(f"kill switch set: {stop} (runs stop before their next iteration; "
          "remove the file to allow new runs)")
    return 0


def cmd_fleet(args) -> int:
    from .fleet import run_fleet

    cfg = load_config(Path(args.path))
    return run_fleet(cfg, config_file=args.config, max_iterations=args.max_iterations)


def cmd_mcp(args) -> int:
    from .mcp_server import serve

    serve(Path(args.path))
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
    from .art import TAGLINE, banner

    parser = argparse.ArgumentParser(
        prog="kelix",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=banner() if sys.stdout.isatty() else f"kelix — {TAGLINE}",
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

    p = sub.add_parser("run", help="run the loop")
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

    p = sub.add_parser("stop", help="set the kill switch (.kelix/STOP)")
    p.add_argument("--path", default=".")
    p.set_defaults(func=cmd_stop)

    p = sub.add_parser("fleet", help="run a coordinated fleet of loops")
    p.add_argument("--path", default=".")
    p.add_argument("--config", default=".kelix/fleet.toml")
    p.add_argument("--max-iterations", type=int, default=None)
    p.set_defaults(func=cmd_fleet)

    p = sub.add_parser("mcp", help="serve Kelix as an MCP server (stdio)")
    p.add_argument("--path", default=".")
    p.set_defaults(func=cmd_mcp)

    p = sub.add_parser("sync", help="mirror tracker issues into the backlog")
    p.add_argument("--path", default=".")
    p.set_defaults(func=cmd_sync)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
