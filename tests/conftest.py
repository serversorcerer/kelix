import stat
import subprocess
from pathlib import Path

import pytest


def sh(args, cwd):
    subprocess.run(args, cwd=str(cwd), check=True, capture_output=True)


def make_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    sh(["git", "init", "-q", "-b", "main"], path)
    sh(["git", "config", "user.email", "kalph-test@example.com"], path)
    sh(["git", "config", "user.name", "Kalph Test"], path)
    kalph = path / ".kalph"
    (kalph / "memory").mkdir(parents=True)
    (kalph / "skills").mkdir()
    (kalph / "backlog.md").write_text(
        "# Backlog\n\n- [ ] T1: demo task | priority: 50 | status: ready | by: owner\n"
    )
    (kalph / "memory" / "project.md").write_text("# Project memory\n")
    (path / "README.md").write_text("fixture repo\n")
    sh(["git", "add", "-A"], path)
    sh(["git", "commit", "-q", "-m", "initial"], path)
    return path


def write_mock_script(mock_dir: Path, name: str, body: str) -> Path:
    mock_dir.mkdir(parents=True, exist_ok=True)
    script = mock_dir / name
    script.write_text("#!/bin/sh\n" + body)
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


@pytest.fixture
def repo(tmp_path):
    return make_repo(tmp_path / "repo")
