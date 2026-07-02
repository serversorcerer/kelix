"""Agent adapters.

An adapter runs ONE fresh agent process with a static prompt and returns its
output. That is the entire interface: the loop core neither knows nor cares
which agent is behind it (see docs/research/prior-art.md).

Adapters:
- kiro: Kiro CLI headless mode (`kiro-cli chat --no-interactive`), the default.
- claude | codex | cursor | gemini: named presets that resolve to `cmd` with
  built-in command templates (see config.ADAPTER_PRESET_COMMANDS).
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
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from .config import ADAPTER_PRESET_COMMANDS, Config


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


def _terminate_process(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def _run_process(
    argv: list[str],
    cwd: Path,
    timeout: int,
    inactivity_timeout: int = 0,
    stdin_text: str | None = None,
    env: dict | None = None,
    live_log: Path | None = None,
) -> AgentResult:
    try:
        proc = subprocess.Popen(
            argv,
            cwd=str(cwd),
            stdin=subprocess.PIPE if stdin_text is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
        )
    except FileNotFoundError as exc:
        raise AdapterError(f"agent command not found: {argv[0]}") from exc

    if stdin_text is not None:
        assert proc.stdin is not None
        proc.stdin.write(stdin_text.encode())
        proc.stdin.close()

    output_chunks: list[bytes] = []
    last_activity = time.monotonic()
    activity_lock = threading.Lock()

    live_fh = None
    if live_log is not None:
        live_log.parent.mkdir(parents=True, exist_ok=True)
        live_fh = open(live_log, "ab")

    def reader() -> None:
        nonlocal last_activity
        assert proc.stdout is not None
        while True:
            # read1: return as soon as ANY bytes arrive (read(4096) would
            # block for the full 4KB, stalling both the live log stream and
            # the inactivity watchdog).
            chunk = proc.stdout.read1(4096)
            if not chunk:
                break
            with activity_lock:
                output_chunks.append(chunk)
                last_activity = time.monotonic()
            if live_fh is not None:
                # Flushed per chunk so `kelix watch` can tail in real time.
                live_fh.write(chunk)
                live_fh.flush()

    reader_thread = threading.Thread(target=reader, daemon=True)
    reader_thread.start()

    start = time.monotonic()
    timed_out = False
    hard_timeout = False

    while proc.poll() is None:
        now = time.monotonic()
        elapsed = now - start

        if timeout > 0 and elapsed >= timeout:
            timed_out = True
            hard_timeout = True
            _terminate_process(proc)
            break

        if inactivity_timeout > 0:
            with activity_lock:
                inactive = now - last_activity
            if inactive >= inactivity_timeout:
                timed_out = True
                _terminate_process(proc)
                break

        time.sleep(0.05)

    reader_thread.join(timeout=5)
    if live_fh is not None:
        live_fh.close()
    out = b"".join(output_chunks).decode(errors="replace")

    if hard_timeout:
        exit_code = 124
    elif proc.returncode is not None:
        exit_code = proc.returncode
    else:
        exit_code = 1

    return AgentResult(exit_code=exit_code, output=out, timed_out=timed_out)


class KiroAdapter:
    """Kiro CLI headless mode. Public surface only (docs/research/kiro-surface.md)."""

    def __init__(self, cfg: Config):
        self.cfg = cfg

    def run(
        self, prompt: str, cwd: Path, live_log: Path | None = None
    ) -> AgentResult:
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
        return _run_process(
            argv,
            cwd,
            self.cfg.agent.timeout_seconds,
            inactivity_timeout=self.cfg.agent.inactivity_timeout_seconds,
            env=env,
            live_log=live_log,
        )


class CmdAdapter:
    """Arbitrary CLI template. How non-Kiro agents (and Kelix-building-Kelix
    on a machine without kiro-cli) plug in."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        if not cfg.agent.command:
            raise AdapterError("cmd adapter requires [agent].command")

    def run(
        self, prompt: str, cwd: Path, live_log: Path | None = None
    ) -> AgentResult:
        template = self.cfg.agent.command
        timeout = self.cfg.agent.timeout_seconds
        inactivity = self.cfg.agent.inactivity_timeout_seconds
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
                return _run_process(
                    argv, cwd, timeout,
                    inactivity_timeout=inactivity, live_log=live_log,
                )
            finally:
                Path(prompt_path).unlink(missing_ok=True)
        if "{prompt}" in template:
            argv = [part.replace("{prompt}", prompt) for part in shlex.split(template)]
            return _run_process(
                argv, cwd, timeout,
                inactivity_timeout=inactivity, live_log=live_log,
            )
        # No token: classic Ralph, prompt on stdin.
        return _run_process(
            shlex.split(template),
            cwd,
            timeout,
            inactivity_timeout=inactivity,
            stdin_text=prompt,
            live_log=live_log,
        )


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

    def run(
        self, prompt: str, cwd: Path, live_log: Path | None = None
    ) -> AgentResult:
        from . import COMPLETION_SENTINEL

        if self._index >= len(self._scripts):
            return AgentResult(exit_code=0, output=COMPLETION_SENTINEL + "\n")
        script = self._scripts[self._index]
        self._index += 1
        return _run_process(
            [str(script)],
            cwd,
            self.cfg.agent.timeout_seconds,
            inactivity_timeout=self.cfg.agent.inactivity_timeout_seconds,
            stdin_text=prompt,
            live_log=live_log,
        )


def make_adapter(cfg: Config):
    name = cfg.agent.adapter
    if name in ADAPTER_PRESET_COMMANDS or name == "cmd":
        return CmdAdapter(cfg)
    return {"kiro": KiroAdapter, "mock": MockAdapter}[name](cfg)
