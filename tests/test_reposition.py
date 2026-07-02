"""P-REPOS acceptance gate (REQ-R3): agent-agnostic reposition without breaking Kiro."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from kelix.config import load_config

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
KIRO_GUIDE = ROOT / "docs" / "kiro.md"

_TOML_FENCE_RE = re.compile(r"```toml\n(.*?)```", re.DOTALL)


def _first_kiro_line(readme_text: str) -> int | None:
    for index, line in enumerate(readme_text.splitlines(), start=1):
        if "kiro" in line.lower():
            return index
    return None


def _toml_blocks(markdown: str) -> list[str]:
    return [match.group(1).strip() for match in _TOML_FENCE_RE.finditer(markdown)]


def test_readme_first_kiro_mention_is_after_line_20():
    first = _first_kiro_line(README.read_text(encoding="utf-8"))
    assert first is not None, "README.md should still mention Kiro as deepest integration"
    assert first > 20, f"first Kiro mention is on line {first}; expected after line 20"


@pytest.mark.parametrize("toml_block", _toml_blocks(KIRO_GUIDE.read_text(encoding="utf-8")))
def test_kiro_guide_toml_blocks_load(toml_block: str, tmp_path: Path):
    kelix_dir = tmp_path / ".kelix"
    kelix_dir.mkdir()
    (kelix_dir / "kelix.toml").write_text(toml_block + "\n", encoding="utf-8")
    cfg = load_config(tmp_path)
    assert cfg.agent.adapter == "kiro"
    assert cfg.agent.kiro_args == ["--agent", "kelix"]
    assert cfg.agent.timeout_seconds == 1800
