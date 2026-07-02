"""Agent guide acceptance (REQ-A2, REQ-A4): TOML snippets and heading parity."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from kelix.config import ADAPTER_PRESET_COMMANDS, load_config

ROOT = Path(__file__).resolve().parents[1]
CURSOR_GUIDE = ROOT / "docs" / "agents" / "cursor.md"
CLAUDE_GUIDE = ROOT / "docs" / "agents" / "claude.md"
CODEX_GUIDE = ROOT / "docs" / "agents" / "codex.md"
GEMINI_GUIDE = ROOT / "docs" / "agents" / "gemini.md"

_TOML_FENCE_RE = re.compile(r"```toml\n(.*?)```", re.DOTALL)
_HEADING_RE = re.compile(r"^## (.+)$", re.MULTILINE)

# Loop-wiring sections shared by docs/agents/*.md (parity with docs/kiro.md
# headless section + P-AGENT CONTEXT.md depth).
AGENT_GUIDE_LOOP_HEADINGS = (
    "The headless adapter",
    "Configure kelix.toml",
    "Install",
    "Auth",
    "Worked example: init → plan → run",
    "Quirks",
    "Troubleshooting",
)


def _toml_blocks(markdown: str) -> list[str]:
    return [match.group(1).strip() for match in _TOML_FENCE_RE.finditer(markdown)]


def _headings(markdown: str) -> list[str]:
    return _HEADING_RE.findall(markdown)


def test_cursor_guide_has_kelix_verified_banner():
    text = CURSOR_GUIDE.read_text(encoding="utf-8")
    assert "**Kelix-verified" in text
    assert ADAPTER_PRESET_COMMANDS["cursor"] in text


def test_cursor_guide_loop_heading_parity():
    headings = _headings(CURSOR_GUIDE.read_text(encoding="utf-8"))
    for required in AGENT_GUIDE_LOOP_HEADINGS:
        assert required in headings, f"missing ## {required}"


@pytest.mark.parametrize("toml_block", _toml_blocks(CURSOR_GUIDE.read_text(encoding="utf-8")))
def test_cursor_guide_toml_blocks_load(toml_block: str, tmp_path: Path):
    kelix_dir = tmp_path / ".kelix"
    kelix_dir.mkdir()
    (kelix_dir / "kelix.toml").write_text(toml_block + "\n", encoding="utf-8")
    load_config(tmp_path)


def test_claude_guide_has_upstream_sourced_banner():
    text = CLAUDE_GUIDE.read_text(encoding="utf-8")
    assert "**Not Kelix CI-tested" in text
    assert ADAPTER_PRESET_COMMANDS["claude"] in text


def test_claude_guide_loop_heading_parity():
    headings = _headings(CLAUDE_GUIDE.read_text(encoding="utf-8"))
    for required in AGENT_GUIDE_LOOP_HEADINGS:
        assert required in headings, f"missing ## {required}"


@pytest.mark.parametrize("toml_block", _toml_blocks(CLAUDE_GUIDE.read_text(encoding="utf-8")))
def test_claude_guide_toml_blocks_load(toml_block: str, tmp_path: Path):
    kelix_dir = tmp_path / ".kelix"
    kelix_dir.mkdir()
    (kelix_dir / "kelix.toml").write_text(toml_block + "\n", encoding="utf-8")
    load_config(tmp_path)


def test_codex_guide_has_upstream_sourced_banner():
    text = CODEX_GUIDE.read_text(encoding="utf-8")
    assert "**Not Kelix CI-tested" in text
    assert ADAPTER_PRESET_COMMANDS["codex"] in text


def test_codex_guide_loop_heading_parity():
    headings = _headings(CODEX_GUIDE.read_text(encoding="utf-8"))
    for required in AGENT_GUIDE_LOOP_HEADINGS:
        assert required in headings, f"missing ## {required}"


@pytest.mark.parametrize("toml_block", _toml_blocks(CODEX_GUIDE.read_text(encoding="utf-8")))
def test_codex_guide_toml_blocks_load(toml_block: str, tmp_path: Path):
    kelix_dir = tmp_path / ".kelix"
    kelix_dir.mkdir()
    (kelix_dir / "kelix.toml").write_text(toml_block + "\n", encoding="utf-8")
    load_config(tmp_path)


def test_gemini_guide_has_upstream_sourced_banner():
    text = GEMINI_GUIDE.read_text(encoding="utf-8")
    assert "**Not Kelix CI-tested" in text
    assert ADAPTER_PRESET_COMMANDS["gemini"] in text


def test_gemini_guide_loop_heading_parity():
    headings = _headings(GEMINI_GUIDE.read_text(encoding="utf-8"))
    for required in AGENT_GUIDE_LOOP_HEADINGS:
        assert required in headings, f"missing ## {required}"


@pytest.mark.parametrize("toml_block", _toml_blocks(GEMINI_GUIDE.read_text(encoding="utf-8")))
def test_gemini_guide_toml_blocks_load(toml_block: str, tmp_path: Path):
    kelix_dir = tmp_path / ".kelix"
    kelix_dir.mkdir()
    (kelix_dir / "kelix.toml").write_text(toml_block + "\n", encoding="utf-8")
    load_config(tmp_path)
