"""Fleet task claims: atomic exclusive locks with heartbeat staleness."""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

CLAIMS_SUBDIR = "fleet/claims"
DEFAULT_STALE_AFTER_S = 900


def _claims_dir(kalph_dir: Path) -> Path:
    return kalph_dir / CLAIMS_SUBDIR


def _claim_path(kalph_dir: Path, task_id: str) -> Path:
    return _claims_dir(kalph_dir) / f"{task_id}.json"


def _read_claim(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _is_stale(claim: dict, stale_after_s: float) -> bool:
    heartbeat = claim.get("heartbeat", claim.get("ts", 0))
    return (time.time() - heartbeat) > stale_after_s


def _write_claim_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def claim_task(
    kalph_dir: Path | str,
    task_id: str,
    agent_id: str,
    branch: str,
    *,
    stale_after_s: float = DEFAULT_STALE_AFTER_S,
) -> bool:
    """Claim a task exclusively. Returns True if this agent holds the claim."""
    root = Path(kalph_dir)
    path = _claim_path(root, task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    now = time.time()

    data = {
        "task": task_id,
        "agent": agent_id,
        "branch": branch,
        "ts": now,
        "heartbeat": now,
    }

    existing = _read_claim(path)
    if existing is not None:
        if not _is_stale(existing, stale_after_s):
            return existing.get("agent") == agent_id
        # Valid but stale: remove it, then race for exclusive re-create below.
        # unlink + O_EXCL guarantees a single winner among concurrent stealers.
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
    elif path.exists():
        # File exists but is unreadable/partial: a concurrent claimer is mid-
        # write. The task is taken; never overwrite (that was a two-winner bug).
        return False

    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        return False
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        return True
    except Exception:
        path.unlink(missing_ok=True)
        raise


def heartbeat(kalph_dir: Path | str, task_id: str, agent_id: str) -> bool:
    """Refresh heartbeat on an owned claim. Returns False if not owned."""
    path = _claim_path(Path(kalph_dir), task_id)
    claim = _read_claim(path)
    if claim is None or claim.get("agent") != agent_id:
        return False
    claim["heartbeat"] = time.time()
    _write_claim_atomic(path, claim)
    return True


def release_claim(kalph_dir: Path | str, task_id: str, agent_id: str) -> bool:
    """Drop a claim if owned by agent_id."""
    path = _claim_path(Path(kalph_dir), task_id)
    claim = _read_claim(path)
    if claim is None or claim.get("agent") != agent_id:
        return False
    path.unlink()
    return True


def is_claimed(
    kalph_dir: Path | str,
    task_id: str,
    stale_after_s: float = DEFAULT_STALE_AFTER_S,
) -> bool:
    """Return True when a non-stale claim exists for the task."""
    claim = _read_claim(_claim_path(Path(kalph_dir), task_id))
    if claim is None:
        return False
    return not _is_stale(claim, stale_after_s)


def list_claims(kalph_dir: Path | str) -> list[dict]:
    """Return all claim records under the fleet claims directory."""
    claims_dir = _claims_dir(Path(kalph_dir))
    if not claims_dir.is_dir():
        return []
    claims: list[dict] = []
    for path in sorted(claims_dir.glob("*.json")):
        claim = _read_claim(path)
        if claim is not None:
            claims.append(claim)
    return claims
