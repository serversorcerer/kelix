"""Git plumbing for the loop.

Safety rails live here: every run gets its own branch (and by default its own
worktree), uncommitted changes are auto-checkpointed so no iteration can
destroy work, and the runner detects whether an iteration actually changed
anything (circuit-breaker input).
"""

from __future__ import annotations

import subprocess
from pathlib import Path


class GitError(Exception):
    pass


def git(args: list[str], cwd: Path, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if check and proc.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed:\n{proc.stdout}")
    return proc.stdout


def is_repo(path: Path) -> bool:
    proc = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=str(path),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc.returncode == 0


def head_sha(cwd: Path) -> str:
    return git(["rev-parse", "HEAD"], cwd).strip()


def last_commit_subject(cwd: Path) -> str:
    """Most recent commit subject on HEAD, or empty when unavailable."""
    return git(["log", "-1", "--format=%s"], cwd, check=False).strip()


def current_branch(cwd: Path) -> str:
    return git(["rev-parse", "--abbrev-ref", "HEAD"], cwd).strip()


def is_dirty(cwd: Path) -> bool:
    return bool(git(["status", "--porcelain"], cwd).strip())


# Files the runner itself writes every iteration (transcripts, run state,
# episode records, claims). They must never be auto-checkpointed: committing
# them would make every iteration look like agent progress and blind the
# no-diff circuit breaker.
RUNNER_BOOKKEEPING = (
    ".kelix/runs",
    ".kelix/memory/episodes.jsonl",
    ".kelix/memory/loop-metrics.json",
    ".kelix/fleet/claims",
)


def checkpoint(cwd: Path, message: str) -> bool:
    """Commit any uncommitted agent changes. Returns True if a commit was made.

    This is the no-lost-work rail: it runs before and after every iteration,
    so an agent that edited files but forgot to commit cannot lose them, and a
    broken half-edit is always recoverable via git history. Runner-owned
    bookkeeping files are excluded — only agent work counts.
    """
    if not is_dirty(cwd):
        return False
    pathspec = ["--", "."] + [f":(exclude){p}" for p in RUNNER_BOOKKEEPING]
    git(["add", "-A", *pathspec], cwd)
    if not git(["diff", "--cached", "--name-only"], cwd).strip():
        return False
    git(["commit", "-m", message, "--no-verify"], cwd)
    return True


def create_run_branch(repo: Path, branch: str) -> None:
    git(["branch", branch, "HEAD"], repo)


def add_worktree(repo: Path, path: Path, branch: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    git(["worktree", "add", str(path), branch], repo)


def remove_worktree(repo: Path, path: Path) -> None:
    git(["worktree", "remove", "--force", str(path)], repo, check=False)


def log_oneline(cwd: Path, n: int = 20) -> str:
    return git(["log", "--oneline", f"-{n}"], cwd, check=False)


PROTECTED_BRANCHES = ("main", "master")


def assert_not_protected(branch: str) -> None:
    if branch in PROTECTED_BRANCHES:
        raise GitError(
            f"refusing to run on protected branch {branch!r}; Kelix only works "
            "Kelix only uses kelix/* run branches; never writes to main"
        )
