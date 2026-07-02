"""Fleet claim file tests."""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from kelix.claims import (
    claim_task,
    heartbeat,
    is_claimed,
    list_claims,
    release_claim,
)


def _kelix_dir(tmp_path: Path) -> Path:
    d = tmp_path / ".kelix"
    d.mkdir()
    return d


def test_single_winner_among_concurrent_claimers(tmp_path):
    kelix = _kelix_dir(tmp_path)
    task_id = "KB7"
    n = 8

    def attempt(agent_id: str) -> bool:
        return claim_task(kelix, task_id, agent_id, f"branch-{agent_id}")

    with ThreadPoolExecutor(max_workers=n) as pool:
        futures = [pool.submit(attempt, f"agent-{i}") for i in range(n)]
        results = [f.result() for f in as_completed(futures)]

    assert sum(results) == 1
    claims = list_claims(kelix)
    assert len(claims) == 1
    assert claims[0]["task"] == task_id
    assert is_claimed(kelix, task_id)


def test_stale_claim_reclaim(tmp_path):
    kelix = _kelix_dir(tmp_path)
    task_id = "KB7"
    claims_dir = kelix / "fleet" / "claims"
    claims_dir.mkdir(parents=True)

    stale_ts = time.time() - 2000
    claim_path = claims_dir / f"{task_id}.json"
    claim_path.write_text(
        json.dumps(
            {
                "task": task_id,
                "agent": "agent-old",
                "branch": "old-branch",
                "ts": stale_ts,
                "heartbeat": stale_ts,
            }
        ),
        encoding="utf-8",
    )

    assert not is_claimed(kelix, task_id, stale_after_s=900)
    assert claim_task(kelix, task_id, "agent-new", "new-branch", stale_after_s=900)

    claims = list_claims(kelix)
    assert len(claims) == 1
    assert claims[0]["agent"] == "agent-new"
    assert claims[0]["branch"] == "new-branch"
    assert is_claimed(kelix, task_id)


def test_release_allows_reclaim(tmp_path):
    kelix = _kelix_dir(tmp_path)
    task_id = "KB7"

    assert claim_task(kelix, task_id, "agent-a", "branch-a")
    assert is_claimed(kelix, task_id)
    assert release_claim(kelix, task_id, "agent-a")
    assert not is_claimed(kelix, task_id)

    assert claim_task(kelix, task_id, "agent-b", "branch-b")
    assert is_claimed(kelix, task_id)
    claims = list_claims(kelix)
    assert claims[0]["agent"] == "agent-b"


def test_wrong_agent_cannot_release_or_heartbeat(tmp_path):
    kelix = _kelix_dir(tmp_path)
    task_id = "KB7"

    assert claim_task(kelix, task_id, "owner", "owner-branch")
    assert not release_claim(kelix, task_id, "intruder")
    assert not heartbeat(kelix, task_id, "intruder")
    assert is_claimed(kelix, task_id)

    claims = list_claims(kelix)
    assert claims[0]["agent"] == "owner"
    before = claims[0]["heartbeat"]
    time.sleep(0.01)
    assert heartbeat(kelix, task_id, "owner")
    after = list_claims(kelix)[0]["heartbeat"]
    assert after >= before
