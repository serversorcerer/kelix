"""DR11: regression gate for post-KV3 doc drift (no ripgrep — pure Python reads)."""

from __future__ import annotations

import re
from pathlib import Path

from kelix.fleet import BUILTIN_ROLES
from kelix.prompt import DEFAULT_TEMPLATE

ROOT = Path(__file__).resolve().parents[1]

BANNED_PHRASES = (
    "open pr",
    "land as pr",
    "opens pr",
    "kelix sync",
    "from kelix.pr",
    "test_pr.py",
)

# Kelix run --pr flag only — not substrings like --proposal-id.
_PR_FLAG_RE = re.compile(r"--pr(?![a-zA-Z])", re.IGNORECASE)


def _assert_no_banned(text: str, *, label: str) -> None:
    lowered = text.lower()
    for phrase in BANNED_PHRASES:
        assert phrase not in lowered, f"{label} contains banned phrase: {phrase!r}"
    assert not _PR_FLAG_RE.search(text), f"{label} contains banned phrase: '--pr'"


def _quickstart_happy_path_text() -> str:
    lines = (ROOT / "docs" / "quickstart.md").read_text(encoding="utf-8").splitlines()
    happy: list[str] = []
    for line in lines:
        if line.startswith("## Operations"):
            break
        happy.append(line)
    return "\n".join(happy)


def test_readme_no_doc_drift_phrases():
    _assert_no_banned(
        (ROOT / "README.md").read_text(encoding="utf-8"),
        label="README.md",
    )


def test_quickstart_happy_path_no_doc_drift_phrases():
    _assert_no_banned(_quickstart_happy_path_text(), label="docs/quickstart.md (happy path)")


def test_memory_and_skills_no_doc_drift_phrases():
    _assert_no_banned(
        (ROOT / "docs" / "memory-and-skills.md").read_text(encoding="utf-8"),
        label="docs/memory-and-skills.md",
    )


def test_fleet_md_no_doc_drift_phrases():
    _assert_no_banned(
        (ROOT / "docs" / "fleet.md").read_text(encoding="utf-8"),
        label="docs/fleet.md",
    )


def test_kiro_md_no_doc_drift_phrases():
    _assert_no_banned(
        (ROOT / "docs" / "kiro.md").read_text(encoding="utf-8"),
        label="docs/kiro.md",
    )


def test_kiro_steering_no_doc_drift_phrases():
    _assert_no_banned(
        (ROOT / "integrations" / "kiro" / "steering" / "kelix.md").read_text(
            encoding="utf-8"
        ),
        label="integrations/kiro/steering/kelix.md",
    )


def test_iteration_template_no_doc_drift_phrases():
    _assert_no_banned(DEFAULT_TEMPLATE, label="DEFAULT_TEMPLATE (iteration prompt)")


def test_gitutil_no_doc_drift_phrases():
    _assert_no_banned(
        (ROOT / "src" / "kelix" / "gitutil.py").read_text(encoding="utf-8"),
        label="src/kelix/gitutil.py",
    )


def test_fleet_builtin_roles_no_doc_drift_phrases():
    combined = "\n".join(BUILTIN_ROLES.values())
    _assert_no_banned(combined, label="BUILTIN_ROLES (fleet.py)")
