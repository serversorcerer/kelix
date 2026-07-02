import json

from kelix.config import Config, MemoryConfig
from kelix.context import score, select
from kelix.memory import episode_digest


def test_score_prefers_matching_tokens():
    idf = {"parser": 2.0, "backlog": 2.0, "noise": 1.0}
    relevant = score("backlog parser module tests", "backlog parser", idf)
    irrelevant = score("unrelated noise topic", "backlog parser", idf)
    assert relevant > irrelevant


def test_select_relevant_old_beats_recent_noise():
    old_relevant = "- [2026-01-01] backlog parser cycle detection -> verified"
    recent_noise = "- [2026-07-02] unrelated deployment fluff -> ok"
    another_noise = "- [2026-07-03] more unrelated fluff -> verified"
    candidates = [old_relevant, recent_noise, another_noise]
    budget = len(old_relevant) + 5
    chosen = select(candidates, "backlog parser cycle", budget)
    assert old_relevant in chosen
    assert recent_noise not in chosen
    assert another_noise not in chosen


def test_select_empty_query_falls_back_to_recency():
    early = "episode-early"
    middle = "episode-middle"
    recent = "episode-recent"
    candidates = [early, middle, recent]
    budget = len(recent) + len(middle) + 1
    chosen = select(candidates, "", budget)
    assert chosen == [middle, recent]


def test_episode_digest_with_query_prefers_relevant_episode(tmp_path):
    cfg = Config(root=tmp_path)
    cfg.memory = MemoryConfig(episodes_in_digest=10)
    ep_dir = tmp_path / ".kelix" / "memory"
    ep_dir.mkdir(parents=True)
    episodes = [
        {
            "ts": "2026-01-01T00:00:00",
            "rationale": "PC10 — backlog parser wave computation",
            "verified": True,
            "failure": "",
        },
        {
            "ts": "2026-07-02T00:00:00",
            "rationale": "KE1 — readme unrelated marketing copy",
            "verified": True,
            "failure": "",
        },
        {
            "ts": "2026-07-03T00:00:00",
            "rationale": "KE2 — docs index unrelated fluff",
            "verified": True,
            "failure": "",
        },
    ]
    (ep_dir / "episodes.jsonl").write_text(
        "\n".join(json.dumps(ep) for ep in episodes) + "\n"
    )
    digest = episode_digest(cfg, query="backlog parser waves", budget_chars=120)
    assert "backlog parser wave computation" in digest
    assert "readme unrelated marketing" not in digest
    assert "docs index unrelated fluff" not in digest
