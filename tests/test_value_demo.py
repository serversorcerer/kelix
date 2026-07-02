"""KV15 scaffold checks for samples/value-demo/; KV17 README value screen."""

import os
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
SAMPLE = ROOT / "samples" / "value-demo"

README_BANNED_PATTERNS = (
    "open pr",
    "land as pr",
    "--pr",
    "kelix sync",
)

QUICKSTART = ROOT / "docs" / "quickstart.md"
SECURITY = ROOT / "docs" / "SECURITY.md"


def test_value_demo_directory_exists():
    assert SAMPLE.is_dir()
    assert (SAMPLE / "GOAL.md").is_file()
    assert (SAMPLE / ".kelix" / "kelix.toml").is_file()
    assert (SAMPLE / ".kelix" / "backlog.md").is_file()


def test_value_demo_pytest_passes():
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=SAMPLE,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_run_demo_script_executable_and_documents_promote():
    script = SAMPLE / "run-demo.sh"
    assert script.is_file()
    assert os.access(script, os.X_OK) or bool(script.stat().st_mode & stat.S_IEXEC)
    body = script.read_text(encoding="utf-8")
    assert "PROMOTE STEP" in body
    assert "status: ready" in body
    assert "kelix run" in body


def test_readme_first_screen_value_sentence_and_demo_link():
    block = "\n".join(README.read_text(encoding="utf-8").splitlines()[:30]).lower()
    assert "well-specified goal" in block
    assert "walk away" in block
    assert "verified commits" in block
    assert "value-demo.md" in block


def test_readme_no_stale_pr_or_sync_claims():
    """DR2: README must not promise --pr, kelix sync, or automated PR opening."""
    text = README.read_text(encoding="utf-8").lower()
    for pattern in README_BANNED_PATTERNS:
        assert pattern not in text, f"README.md contains banned pattern: {pattern!r}"


def _quickstart_happy_path_text() -> str:
    lines = QUICKSTART.read_text(encoding="utf-8").splitlines()
    happy: list[str] = []
    for line in lines:
        if line.startswith("## Operations"):
            break
        happy.append(line)
    return "\n".join(happy).lower()


def test_quickstart_happy_path_no_stale_pr_or_sync_claims():
    """DR10: quickstart steps 1–6 must not promise --pr, kelix sync, or open PRs."""
    text = _quickstart_happy_path_text()
    for pattern in README_BANNED_PATTERNS:
        assert pattern not in text, f"quickstart happy path contains banned pattern: {pattern!r}"


def test_security_no_stale_pr_automation_claims():
    """DR10: SECURITY summary must match post-KV3 (no --pr, sync, or PR automation)."""
    text = SECURITY.read_text(encoding="utf-8").lower()
    for pattern in README_BANNED_PATTERNS:
        assert pattern not in text, f"SECURITY.md contains banned pattern: {pattern!r}"
    assert "pr automation" not in text
