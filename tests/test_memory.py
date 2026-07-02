import json

from kelix.config import Config, MemoryConfig
from kelix.loop import IterationRecord, RunResult
from kelix.memory import (
    _parse_skill,
    episode_digest,
    load_episodes,
    record_episode,
    skills_digest,
    write_retrospective,
)


def _cfg(root) -> Config:
    return Config(root=root)


def test_record_and_load_episodes_round_trip(tmp_path):
    cfg = _cfg(tmp_path)
    (tmp_path / ".kelix").mkdir()
    rec = IterationRecord(
        index=1,
        started_at="2026-07-02T00:00:00",
        rationale="KB1 — backlog parser",
        made_progress=True,
        verified=True,
        failure="",
        duration_s=2.5,
    )
    record_episode(cfg, rec, agent_id="solo")
    episodes = load_episodes(cfg)
    assert len(episodes) == 1
    assert episodes[0]["iteration"] == 1
    assert episodes[0]["rationale"] == "KB1 — backlog parser"
    assert episodes[0]["verified"] is True
    assert episodes[0]["progress"] is True
    assert episodes[0]["agent"] == "solo"
    assert episodes[0]["duration_s"] == 2.5


def test_load_episodes_skips_corrupt_lines(tmp_path):
    cfg = _cfg(tmp_path)
    ep_dir = tmp_path / ".kelix" / "memory"
    ep_dir.mkdir(parents=True)
    (ep_dir / "episodes.jsonl").write_text(
        json.dumps({"iteration": 1, "rationale": "good"}) + "\n"
        "not valid json\n"
        "\n"
        + json.dumps({"iteration": 2, "rationale": "also good"}) + "\n"
    )
    episodes = load_episodes(cfg)
    assert len(episodes) == 2
    assert episodes[0]["iteration"] == 1
    assert episodes[1]["iteration"] == 2


def test_episode_digest_includes_rationale_and_failure(tmp_path):
    cfg = _cfg(tmp_path)
    ep_dir = tmp_path / ".kelix" / "memory"
    ep_dir.mkdir(parents=True)
    (ep_dir / "episodes.jsonl").write_text(
        json.dumps(
            {
                "ts": "2026-07-02T00:00:00",
                "rationale": "KB1 — verified work",
                "verified": True,
                "failure": "",
            }
        )
        + "\n"
        + json.dumps(
            {
                "ts": "2026-07-02T00:01:00",
                "rationale": "KB2 — broken build",
                "verified": False,
                "failure": "pytest failed",
            }
        )
        + "\n"
    )
    digest = episode_digest(cfg)
    assert "KB1 — verified work" in digest
    assert "verified" in digest
    assert "KB2 — broken build" in digest
    assert "FAILED: pytest failed" in digest


def test_episode_digest_respects_episodes_in_digest(tmp_path):
    cfg = _cfg(tmp_path)
    cfg.memory = MemoryConfig(episodes_in_digest=2)
    ep_dir = tmp_path / ".kelix" / "memory"
    ep_dir.mkdir(parents=True)
    lines = [
        json.dumps({"ts": f"2026-07-02T00:0{i}:00", "rationale": f"episode-{i}"})
        for i in range(3)
    ]
    (ep_dir / "episodes.jsonl").write_text("\n".join(lines) + "\n")
    digest = episode_digest(cfg)
    assert "episode-0" not in digest
    assert "episode-1" in digest
    assert "episode-2" in digest


def test_parse_skill_extracts_frontmatter(tmp_path):
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text(
        "---\nname: deploy-app\ndescription: Deploy to staging\n---\n\n# Steps\n"
    )
    assert _parse_skill(skill_file) == ("deploy-app", "Deploy to staging")


def test_parse_skill_returns_none_without_frontmatter(tmp_path):
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text("# Just markdown\nNo frontmatter here.\n")
    assert _parse_skill(skill_file) is None

    incomplete = tmp_path / "incomplete.md"
    incomplete.write_text("---\nname: orphan\n")
    assert _parse_skill(incomplete) is None


def test_skills_digest_lists_name_description_and_path(tmp_path):
    cfg = _cfg(tmp_path)
    skill_dir = tmp_path / ".kelix" / "skills" / "demo-skill"
    skill_dir.mkdir(parents=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("---\nname: demo-skill\ndescription: A demo skill\n---\n")
    digest = skills_digest(cfg)
    assert "demo-skill: A demo skill" in digest
    assert "full steps:" in digest
    assert str(skill_md) in digest


def test_skills_digest_excludes_proposed_until_promoted(tmp_path):
    cfg = _cfg(tmp_path)
    skill_md = (
        tmp_path / ".kelix" / "skills" / "_proposed" / "candidate-skill" / "SKILL.md"
    )
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text(
        "---\nname: candidate-skill\ndescription: Awaiting promotion\n---\n"
    )
    assert skills_digest(cfg) == ""

    promoted_dir = tmp_path / ".kelix" / "skills" / "candidate-skill"
    promoted_dir.mkdir(parents=True)
    skill_md.rename(promoted_dir / "SKILL.md")
    skill_md.parent.rmdir()
    (tmp_path / ".kelix" / "skills" / "_proposed").rmdir()

    digest = skills_digest(cfg)
    assert "candidate-skill: Awaiting promotion" in digest


def test_write_retrospective_with_failures(tmp_path):
    cfg = _cfg(tmp_path)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    result = RunResult(
        run_id="run-20260702",
        status="completed",
        branch="kelix/run-20260702",
        workdir=str(tmp_path),
        iterations=[
            IterationRecord(index=1, started_at="", rationale="KB1 — done", verified=True),
            IterationRecord(
                index=2,
                started_at="",
                rationale="KB2 — stuck",
                failure="pytest failed",
            ),
        ],
    )
    write_retrospective(cfg, result, run_dir)
    retro = (run_dir / "retrospective.md").read_text()
    assert "status: **completed**" in retro
    assert "KB1 — done" in retro
    assert "KB2 — stuck" in retro
    assert "FAIL (pytest failed)" in retro
    assert "## For the owner" in retro
    assert "iteration 2 needs attention: pytest failed" in retro


def test_write_retrospective_without_failures(tmp_path):
    cfg = _cfg(tmp_path)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    result = RunResult(
        run_id="run-clean",
        status="completed",
        branch="kelix/run-clean",
        workdir=str(tmp_path),
        iterations=[
            IterationRecord(index=1, started_at="", rationale="All good", verified=True),
        ],
    )
    write_retrospective(cfg, result, run_dir)
    retro = (run_dir / "retrospective.md").read_text()
    assert "status: **completed**" in retro
    assert "## For the owner" not in retro
