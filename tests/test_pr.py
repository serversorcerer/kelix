"""PR flow module tests."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from kelix.config import Config, VerifyConfig
from kelix.loop import IterationRecord, RunResult
from kelix.pr import build_pr_body, open_pr


def _cfg(root: Path, commands: list[str] | None = None) -> Config:
    cfg = Config(root=root)
    if commands is not None:
        cfg.verify = VerifyConfig(commands=commands)
    return cfg


def _result(
    branch: str = "kelix/run-test",
    workdir: str = "/tmp/workdir",
    **kwargs,
) -> RunResult:
    defaults = {
        "run_id": "20260702-003053",
        "status": "completed",
        "branch": branch,
        "workdir": workdir,
        "iterations": [
            IterationRecord(
                index=1,
                started_at="",
                rationale="KB6 — PR flow module",
                verified=True,
            ),
        ],
    }
    defaults.update(kwargs)
    return RunResult(**defaults)


@pytest.fixture
def record_subprocess(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(args, **kwargs):
        calls.append(list(args))
        if args and args[0] == "gh":
            return MagicMock(returncode=0, stdout="https://github.com/org/repo/pull/42\n")
        return MagicMock(returncode=0, stdout="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    return calls


def test_refuses_main_branch(tmp_path, record_subprocess):
    result = _result(branch="main")
    assert open_pr(_cfg(tmp_path), result, tmp_path / "run") is None
    assert record_subprocess == []


def test_refuses_master_branch(tmp_path, record_subprocess):
    result = _result(branch="master")
    assert open_pr(_cfg(tmp_path), result, tmp_path / "run") is None
    assert record_subprocess == []


def test_refuses_empty_branch(tmp_path, record_subprocess):
    result = _result(branch="")
    assert open_pr(_cfg(tmp_path), result, tmp_path / "run") is None
    assert record_subprocess == []


def test_push_before_gh(tmp_path, record_subprocess):
    result = _result()
    url = open_pr(_cfg(tmp_path, ["pytest -q"]), result, tmp_path / "run")
    assert url == "https://github.com/org/repo/pull/42"
    assert len(record_subprocess) == 2
    assert record_subprocess[0][:3] == ["git", "push", "-u"]
    assert record_subprocess[0][3:] == ["origin", "kelix/run-test"]
    assert record_subprocess[1][:3] == ["gh", "pr", "create"]


def test_no_force_anywhere(tmp_path, monkeypatch):
    calls: list[list[str]] = []

    def fake_run(args, **kwargs):
        calls.append(list(args))
        if args and args[0] == "gh":
            return MagicMock(returncode=0, stdout="https://github.com/org/repo/pull/1\n")
        return MagicMock(returncode=0, stdout="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    open_pr(_cfg(tmp_path), _result(), tmp_path / "run")
    for call in calls:
        assert "--force" not in call


def test_body_contains_verification_evidence(tmp_path, record_subprocess):
    result = _result(
        iterations=[
            IterationRecord(
                index=1,
                started_at="",
                rationale="KB6 — PR flow module",
                verified=True,
            ),
            IterationRecord(
                index=2,
                started_at="",
                rationale="KB7 — fleet claims",
                verified=False,
            ),
        ]
    )
    open_pr(_cfg(tmp_path, ["pytest -q", "ruff check src tests"]), result, tmp_path / "run")
    gh_call = record_subprocess[1]
    body_index = gh_call.index("--body") + 1
    body = gh_call[body_index]
    assert "pytest -q" in body
    assert "ruff check src tests" in body
    assert "iteration 1: verified" in body
    assert "iteration 2: failed" in body
    assert "KB6" in body
    assert "KB7" in body
    assert "Opened by Kelix run 20260702-003053" in body


def test_build_pr_body_standalone(tmp_path):
    result = _result()
    body = build_pr_body(_cfg(tmp_path, ["pytest -q"]), result)
    assert "## Verification evidence" in body
    assert "pytest -q" in body
    assert "iteration 1: verified" in body


def test_returns_none_when_gh_fails(tmp_path, monkeypatch):
    def fake_run(args, **kwargs):
        if args and args[0] == "gh":
            return MagicMock(returncode=1, stdout="error creating PR\n")
        return MagicMock(returncode=0, stdout="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert open_pr(_cfg(tmp_path), _result(), tmp_path / "run") is None


def test_returns_none_when_push_fails(tmp_path, monkeypatch):
    def fake_run(args, **kwargs):
        if args and args[0] == "git":
            return MagicMock(returncode=1, stdout="push rejected\n")
        return MagicMock(returncode=0, stdout="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert open_pr(_cfg(tmp_path), _result(), tmp_path / "run") is None
