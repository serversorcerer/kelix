"""P-REPOS acceptance gate (REQ-R3): agent-agnostic reposition without breaking Kiro."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"


def _first_kiro_line(readme_text: str) -> int | None:
    for index, line in enumerate(readme_text.splitlines(), start=1):
        if "kiro" in line.lower():
            return index
    return None


def test_readme_first_kiro_mention_is_after_line_20():
    first = _first_kiro_line(README.read_text(encoding="utf-8"))
    assert first is not None, "README.md should still mention Kiro as deepest integration"
    assert first > 20, f"first Kiro mention is on line {first}; expected after line 20"
