"""Kelix CLI art: the banner and themed output helpers.

Rules: stdlib only; color only when stdout is a TTY and NO_COLOR is unset;
plain-text fallback everywhere. The art must never break machine-readable
output — banners go to stderr-safe surfaces (help, init, run start), never
into transcripts, logs the runner parses, or piped output.
"""

from __future__ import annotations

import os
import sys

# Double-helix strand, drawn simply enough to survive any terminal font.
HELIX = r"""
      ╭─╮   ╭─╮   ╭─╮   ╭─╮
   ╭──┼─╳───┼─╳───┼─╳───┼─╳──▲
   ╰──┼─╳───┼─╳───┼─╳───┼─╳──╯
      ╰─╯   ╰─╯   ╰─╯   ╰─╯
"""

WORDMARK = r"""
  ██╗  ██╗███████╗██╗     ██╗██╗  ██╗
  ██║ ██╔╝██╔════╝██║     ██║╚██╗██╔╝
  █████╔╝ █████╗  ██║     ██║ ╚███╔╝
  ██╔═██╗ ██╔══╝  ██║     ██║ ██╔██╗
  ██║  ██╗███████╗███████╗██║██╔╝ ██╗
  ╚═╝  ╚═╝╚══════╝╚══════╝╚═╝╚═╝  ╚═╝
"""

TAGLINE = "the loop that climbs — ralph runs in circles; kelix comes back higher"

# 256-color gradient, deep teal -> spring green: ascent.
_GRADIENT = (30, 36, 42, 48, 84, 120)
_RESET = "\x1b[0m"
_DIM = "\x1b[2m"
_BOLD = "\x1b[1m"


def _color_enabled(stream=None) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("KELIX_NO_ART"):
        return False
    stream = stream or sys.stdout
    return hasattr(stream, "isatty") and stream.isatty()


def _gradient_lines(text: str) -> str:
    lines = [line for line in text.splitlines() if line.strip() or True]
    out = []
    for i, line in enumerate(lines):
        shade = _GRADIENT[min(i * len(_GRADIENT) // max(len(lines), 1), len(_GRADIENT) - 1)]
        out.append(f"\x1b[38;5;{shade}m{line}{_RESET}")
    return "\n".join(out)


def banner(stream=None) -> str:
    """The full startup banner: gradient wordmark + helix + tagline."""
    if os.environ.get("KELIX_NO_ART"):
        return "kelix — " + TAGLINE
    art = WORDMARK.rstrip("\n") + "\n" + HELIX.rstrip("\n")
    if _color_enabled(stream):
        return (
            _gradient_lines(art)
            + f"\n  {_DIM}{TAGLINE}{_RESET}\n"
        )
    return art + f"\n  {TAGLINE}\n"


def strip(width: int = 34) -> str:
    """A one-line helix divider for section breaks in CLI output."""
    unit = "◟◠◞◡"
    line = (unit * (width // len(unit) + 1))[:width]
    return line


def say(msg: str, kind: str = "info", stream=None) -> str:
    """Theme a status line: a spiral glyph + color per kind, plain when piped."""
    glyphs = {
        "info": "◌",
        "ok": "◉",
        "warn": "◍",
        "fail": "◎",
        "climb": "↻",
    }
    colors = {"info": 36, "ok": 84, "warn": 214, "fail": 203, "climb": 120}
    glyph = glyphs.get(kind, "◌")
    if _color_enabled(stream):
        return f"\x1b[38;5;{colors.get(kind, 36)}m{glyph}{_RESET} {msg}"
    return f"{glyph} {msg}"


def next_steps(steps: list[str]) -> str:
    """Render the numbered onramp steps with the climb glyph."""
    lines = [say("next moves:", "climb")]
    for i, step in enumerate(steps, 1):
        lines.append(f"    {i}. {step}")
    return "\n".join(lines)


def run_complete_receipt(
    *,
    run_id: str,
    status: str,
    iteration_count: int,
    verified_count: int,
    verify_commands: list[str],
    diagnosis: str = "",
) -> str:
    """Themed run-end summary: status, verify gate, verified-done count."""
    status_kind = {
        "completed": "ok",
        "max_iterations": "ok",
        "circuit_breaker": "fail",
        "killed": "warn",
    }.get(status, "info")
    noun = "iteration" if iteration_count == 1 else "iterations"
    lines = [
        say(
            f"run {run_id} finished: {status} "
            f"({iteration_count} {noun}, {verified_count} verified-done)",
            status_kind,
        ),
    ]
    if verify_commands:
        gate = "; ".join(verify_commands)
        lines.append(say(f"verify gate: {gate}", "info"))
    else:
        lines.append(say("verify gate: none configured", "info"))
    if diagnosis:
        lines.append(say(f"diagnosis: {diagnosis}", "warn"))
    return "\n".join(lines)
