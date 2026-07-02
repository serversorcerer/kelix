"""Verification gate.

"Done" is not the agent's claim — it is these commands exiting 0. The runner
executes them after every iteration in the working directory; the loop uses
the result to decide whether to honor the completion sentinel and whether the
iteration counts as a failure.
"""

from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .config import Config


@dataclass
class CommandResult:
    command: str
    exit_code: int
    output_tail: str = ""
    timed_out: bool = False


@dataclass
class VerifyReport:
    results: list[CommandResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(r.exit_code == 0 and not r.timed_out for r in self.results)

    def summary(self) -> str:
        lines = []
        for r in self.results:
            if r.timed_out:
                status = "TIMEOUT"
            else:
                status = "ok" if r.exit_code == 0 else f"exit {r.exit_code}"
            lines.append(f"{r.command}: {status}")
            if r.exit_code != 0 and r.output_tail:
                lines.append(r.output_tail)
        return "\n".join(lines)


def run_verification(cfg: Config, workdir: Path) -> VerifyReport | None:
    """Run all configured verify commands. Returns None when none are
    configured (loop treats that as 'nothing to gate on', not success)."""
    if not cfg.verify.commands:
        return None
    report = VerifyReport()
    for command in cfg.verify.commands:
        # Expand $VARS so configs can stay machine-portable (no hardcoded
        # absolute paths); commands still run without a shell.
        expanded = os.path.expandvars(command)
        try:
            proc = subprocess.run(
                shlex.split(expanded),
                cwd=str(workdir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=cfg.verify.timeout_seconds,
            )
            tail = "\n".join((proc.stdout or "").splitlines()[-15:])
            report.results.append(
                CommandResult(command=command, exit_code=proc.returncode, output_tail=tail)
            )
        except subprocess.TimeoutExpired:
            report.results.append(
                CommandResult(command=command, exit_code=124, timed_out=True)
            )
        except FileNotFoundError:
            report.results.append(
                CommandResult(command=command, exit_code=127, output_tail="command not found")
            )
        if report.results[-1].exit_code != 0:
            break  # fail fast; later commands often depend on earlier ones
    return report
