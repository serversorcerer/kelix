"""Kelix as an MCP server (stdio, JSON-RPC 2.0).

Lets any MCP-capable agent (Kiro first) drive Kelix through tool calls: start a
run, check status, inspect memory, stop. Deliberately dependency-free — a
minimal, auditable implementation of the subset of MCP needed here
(initialize, tools/list, tools/call) over newline-delimited JSON on stdio.

Register with Kiro CLI:
    kiro-cli mcp add --name kelix --command "kelix mcp" --scope workspace

Tool schema is documented in docs/mcp.md and returned by tools/list.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from . import __version__
from .config import load_config

PROTOCOL_VERSION = "2024-11-05"

TOOLS = [
    {
        "name": "kelix_run",
        "description": "Start a Kelix loop run against the repository. Runs "
        "synchronously and returns the run status and per-iteration summary. "
        "Use max_iterations to bound cost.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "max_iterations": {"type": "integer", "minimum": 1},
                "role": {"type": "string", "description": "optional role text"},
            },
        },
    },
    {
        "name": "kelix_status",
        "description": "Show current run/fleet status derived from coordination "
        "files: task claims, recent runs, mailbox notes, and the kill switch.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "kelix_memory",
        "description": "Inspect Kelix's memory: project memory, recent episode "
        "records, and earned skills.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "episodes": {"type": "integer", "minimum": 0, "default": 10}
            },
        },
    },
    {
        "name": "kelix_stop",
        "description": "Set the kill switch (.kelix/STOP) so active/future runs "
        "halt before their next iteration.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


class MCPServer:
    def __init__(self, root: Path):
        self.root = root

    # -- tool implementations ------------------------------------------------

    def _tool_run(self, args: dict) -> str:
        from .loop import Runner

        cfg = load_config(self.root)
        runner = Runner(cfg, role=args.get("role", ""))
        result = runner.run(max_iterations=args.get("max_iterations"), log=lambda *_: None)
        summary = [f"run {result.run_id}: {result.status} (branch {result.branch})"]
        for rec in result.iterations:
            outcome = rec.failure or ("verified" if rec.verified else "ok")
            summary.append(f"  iter {rec.index}: {rec.rationale or '-'} -> {outcome}")
        if result.diagnosis:
            summary.append(f"diagnosis: {result.diagnosis}")
        return "\n".join(summary)

    def _tool_status(self, args: dict) -> str:
        from .fleet import render_status

        return render_status(load_config(self.root))

    def _tool_memory(self, args: dict) -> str:
        from .memory import episode_digest, skills_digest

        cfg = load_config(self.root)
        project = cfg.kelix_dir / "memory" / "project.md"
        parts = ["# Project memory"]
        parts.append(project.read_text(encoding="utf-8") if project.is_file() else "(none)")
        parts.append("\n# Recent episodes")
        parts.append(episode_digest(cfg) or "(none)")
        parts.append("\n# Skills")
        parts.append(skills_digest(cfg) or "(none)")
        return "\n".join(parts)

    def _tool_stop(self, args: dict) -> str:
        cfg = load_config(self.root)
        stop = cfg.kelix_dir / "STOP"
        stop.parent.mkdir(parents=True, exist_ok=True)
        stop.write_text("stop requested via MCP\n", encoding="utf-8")
        return f"kill switch set: {stop}"

    def _dispatch_tool(self, name: str, args: dict) -> str:
        impl = {
            "kelix_run": self._tool_run,
            "kelix_status": self._tool_status,
            "kelix_memory": self._tool_memory,
            "kelix_stop": self._tool_stop,
        }.get(name)
        if impl is None:
            raise KeyError(f"unknown tool {name!r}")
        return impl(args or {})

    # -- JSON-RPC ------------------------------------------------------------

    def handle(self, request: dict) -> dict | None:
        method = request.get("method")
        req_id = request.get("id")
        # Notifications (no id) get no response.
        if method == "initialize":
            return self._ok(req_id, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "kelix", "version": __version__},
            })
        if method == "notifications/initialized":
            return None
        if method == "tools/list":
            return self._ok(req_id, {"tools": TOOLS})
        if method == "tools/call":
            params = request.get("params", {})
            name = params.get("name", "")
            try:
                text = self._dispatch_tool(name, params.get("arguments", {}))
                return self._ok(req_id, {
                    "content": [{"type": "text", "text": text}],
                    "isError": False,
                })
            except Exception as exc:
                return self._ok(req_id, {
                    "content": [{"type": "text", "text": f"error: {exc}"}],
                    "isError": True,
                })
        if req_id is None:
            return None
        return self._err(req_id, -32601, f"method not found: {method}")

    @staticmethod
    def _ok(req_id, result) -> dict:
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    @staticmethod
    def _err(req_id, code, message) -> dict:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def serve(root: Path, stdin=None, stdout=None) -> None:
    """Run the stdio JSON-RPC loop until EOF."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    server = MCPServer(root.resolve())
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = server.handle(request)
        if response is not None:
            stdout.write(json.dumps(response) + "\n")
            stdout.flush()
