"""Agent adapters.

An adapter runs ONE fresh agent process with a static prompt and returns its
output. That is the entire interface: the loop core neither knows nor cares
which agent is behind it (see docs/research/prior-art.md).

Adapters:
- kiro: Kiro CLI headless mode (`kiro-cli chat --no-interactive`), the default.
- cmd:  arbitrary command template, e.g. any coding-agent CLI. Tokens
        {prompt_file} and {prompt} are substituted; with neither token, the
        prompt is piped to stdin (the classic `cat PROMPT.md | agent`).
- mock: scripted responses from a directory of executables, for tests/CI.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .config import Config


@dataclass
class AgentResult:
    exit_code: int
    output: str
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


class AdapterError(Exception):
    pass


def _run_process(
    argv: list[str],
    cwd: Path,
    timeout: int,
    stdin_text: str | None = None,
    env: dict | None = None,
) -> AgentResult:
    try:
        proc = subprocess.run(
            argv,
            cwd=str(cwd),
            input=stdin_text,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        out = exc.output or ""
        if isinstance(out, bytes):
            out = out.decode(errors="replace")
        return AgentResult(exit_code=124, output=out, timed_out=True)
    except FileNotFoundError as exc:
        raise AdapterError(f"agent command not found: {argv[0]}") from exc
    return AgentResult(exit_code=proc.returncode, output=proc.stdout or "")


class KiroAdapter:
    """Kiro CLI headless mode. Public surface only (docs/research/kiro-surface.md)."""

    def __init__(self, cfg: Config):
        self.cfg = cfg

    def run(self, prompt: str, cwd: Path) -> AgentResult:
        env = dict(os.environ)
        env.setdefault("KIRO_LOG_NO_COLOR", "1")
        argv = [
            "kiro-cli",
            "chat",
            "--no-interactive",
            "--trust-all-tools",
            *self.cfg.agent.kiro_args,
            prompt,
        ]
        return _run_process(argv, cwd, self.cfg.agent.timeout_seconds, env=env)


class CmdAdapter:
    """Arbitrary CLI template. How non-Kiro agents (and Kelix-building-Kelix
    on a machine without kiro-cli) plug in."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        if not cfg.agent.command:
            raise AdapterError("cmd adapter requires [agent].command")

    def run(self, prompt: str, cwd: Path) -> AgentResult:
        template = self.cfg.agent.command
        timeout = self.cfg.agent.timeout_seconds
        if "{prompt_file}" in template:
            with tempfile.NamedTemporaryFile(
                "w", suffix=".md", prefix="kelix-prompt-", delete=False
            ) as tf:
                tf.write(prompt)
                prompt_path = tf.name
            try:
                argv = [
                    part.replace("{prompt_file}", prompt_path)
                    for part in shlex.split(template)
                ]
                return _run_process(argv, cwd, timeout)
            finally:
                Path(prompt_path).unlink(missing_ok=True)
        if "{prompt}" in template:
            argv = [part.replace("{prompt}", prompt) for part in shlex.split(template)]
            return _run_process(argv, cwd, timeout)
        # No token: classic Ralph, prompt on stdin.
        return _run_process(shlex.split(template), cwd, timeout, stdin_text=prompt)


class MockAdapter:
    """Deterministic scripted agent for tests.

    [agent].mock_dir contains executables named 001*, 002*, ... run in sorted
    order, one per iteration. Each receives the prompt on stdin and runs with
    cwd set to the (isolated) repo; its stdout is the agent output. When the
    scripts run out, the mock emits the completion sentinel.
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg
        mock_dir = cfg.agent.mock_dir
        if not mock_dir:
            raise AdapterError("mock adapter requires [agent].mock_dir")
        self.dir = (cfg.root / mock_dir).resolve()
        if not self.dir.is_dir():
            raise AdapterError(f"mock_dir not found: {self.dir}")
        self._scripts = sorted(p for p in self.dir.iterdir() if os.access(p, os.X_OK))
        self._index = 0

    def run(self, prompt: str, cwd: Path) -> AgentResult:
        from . import COMPLETION_SENTINEL

        if self._index >= len(self._scripts):
            return AgentResult(exit_code=0, output=COMPLETION_SENTINEL + "\n")
        script = self._scripts[self._index]
        self._index += 1
        return _run_process(
            [str(script)], cwd, self.cfg.agent.timeout_seconds, stdin_text=prompt
        )


def make_adapter(cfg: Config):
    return {"kiro": KiroAdapter, "cmd": CmdAdapter, "mock": MockAdapter}[
        cfg.agent.adapter
    ](cfg)
