"""Kalph command-line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .config import ConfigError, load_config

BACKLOG_TEMPLATE = """\
# Kalph backlog

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
# Kalph configuration. Every field is optional; defaults are safe.

[agent]
adapter = "kiro"          # kiro | cmd | mock

[loop]
max_iterations = 25
circuit_breaker_threshold = 3

[verify]
# Commands that define "done". All must exit 0.
commands = []

[git]
isolation = "worktree"    # worktree | branch | none
"""


def cmd_init(args) -> int:
    root = Path(args.path).resolve()
    kalph = root / ".kalph"
    created = []
    for rel, content in [
        ("backlog.md", BACKLOG_TEMPLATE),
        ("memory/project.md", PROJECT_MEMORY_TEMPLATE),
        ("kalph.toml", CONFIG_TEMPLATE),
    ]:
        path = kalph / rel
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            created.append(str(path.relative_to(root)))
    (kalph / "skills").mkdir(exist_ok=True)
    (kalph / "prompts").mkdir(exist_ok=True)
    if args.from_spec:
        from .kiro import import_spec

        count = import_spec(root, args.from_spec)
        print(f"imported {count} tasks from .kiro/specs/{args.from_spec}/tasks.md")
    print("initialized: " + (", ".join(created) if created else "(already initialized)"))
    print("next: edit .kalph/backlog.md, set [verify] commands in .kalph/kalph.toml, "
          "then `kalph run`")
    return 0


def cmd_run(args) -> int:
    from .loop import LoopError, Runner

    try:
        cfg = load_config(Path(args.path))
        runner = Runner(cfg, role=args.role or "")
        result = runner.run(max_iterations=args.max_iterations)
    except (ConfigError, LoopError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0 if result.status in ("completed", "max_iterations") else 1


def cmd_status(args) -> int:
    from .fleet import render_status

    cfg = load_config(Path(args.path))
    print(render_status(cfg))
    return 0


def cmd_stop(args) -> int:
    cfg = load_config(Path(args.path))
    stop = cfg.kalph_dir / "STOP"
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="kalph",
        description="Kalph: the Ralph loop, rebuilt for Kiro.",
    )
    parser.add_argument("--version", action="version", version=f"kalph {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="initialize .kalph/ in a repository")
    p.add_argument("--path", default=".")
    p.add_argument("--from-spec", default="", help="seed backlog from .kiro/specs/<name>/tasks.md")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("run", help="run the loop")
    p.add_argument("--path", default=".")
    p.add_argument("--max-iterations", type=int, default=None)
    p.add_argument("--role", default="", help="role text to inject into the prompt")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("status", help="show run/fleet status from coordination files")
    p.add_argument("--path", default=".")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("stop", help="set the kill switch (.kalph/STOP)")
    p.add_argument("--path", default=".")
    p.set_defaults(func=cmd_stop)

    p = sub.add_parser("fleet", help="run a coordinated fleet of loops")
    p.add_argument("--path", default=".")
    p.add_argument("--config", default=".kalph/fleet.toml")
    p.add_argument("--max-iterations", type=int, default=None)
    p.set_defaults(func=cmd_fleet)

    p = sub.add_parser("mcp", help="serve Kalph as an MCP server (stdio)")
    p.add_argument("--path", default=".")
    p.set_defaults(func=cmd_mcp)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
