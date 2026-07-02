from kelix.config import load_config
from kelix.prompt import (
    DEFAULT_TEMPLATE,
    PHASE_CONTEXT_BANNER,
    assemble_prompt,
    compute_slot_budgets,
    format_phase_context,
    load_phase_context,
    load_template,
    relevance_query_for_task,
)


def test_default_template_used_when_no_repo_prompt(tmp_path):
    cfg = load_config(tmp_path)
    assert load_template(cfg) == DEFAULT_TEMPLATE


def test_repo_prompt_file_overrides_default(tmp_path):
    cfg = load_config(tmp_path)
    prompt_path = tmp_path / cfg.loop.prompt_file
    prompt_path.parent.mkdir(parents=True)
    prompt_path.write_text("custom {{MEMORY_DIGEST}}")
    assert load_template(cfg) == "custom {{MEMORY_DIGEST}}"


def test_slots_filled_with_placeholders_when_empty(tmp_path):
    cfg = load_config(tmp_path)
    out, _manifest = assemble_prompt(DEFAULT_TEMPLATE, cfg)
    assert "{{" not in out
    assert "(no state file — flat-backlog mode)" in out
    assert "(no episodes yet)" in out
    assert "(no project memory yet)" in out
    assert "(no skills yet)" in out
    assert "solo builder" in out


def test_slots_filled_with_data(tmp_path):
    cfg = load_config(tmp_path)
    out, _manifest = assemble_prompt(
        DEFAULT_TEMPLATE, cfg, memory_digest="ep1 ok", skills="skill-a", role="Role: verifier."
    )
    assert "ep1 ok" in out
    assert "skill-a" in out
    assert "Role: verifier." in out


def test_digest_budget_enforced(tmp_path):
    (tmp_path / "kelix.toml").write_text("[memory]\ndigest_max_chars = 50\n")
    cfg = load_config(tmp_path)
    out, _manifest = assemble_prompt(DEFAULT_TEMPLATE, cfg, memory_digest="x" * 500)
    assert "truncated to 50 chars" in out
    # The raw 500-char blob must not appear.
    assert "x" * 51 not in out


def test_contract_and_security_present_in_default():
    assert "KELIX COMPLETE" in DEFAULT_TEMPLATE
    assert "exactly ONE task" in DEFAULT_TEMPLATE
    assert "Read `.kelix/STATE.md` first" in DEFAULT_TEMPLATE
    assert "DATA" in DEFAULT_TEMPLATE
    assert "Never push directly to main" in DEFAULT_TEMPLATE


def test_state_slot_before_episode_digest():
    state_pos = DEFAULT_TEMPLATE.index("{{STATE}}")
    digest_pos = DEFAULT_TEMPLATE.index("{{MEMORY_DIGEST}}")
    assert state_pos < digest_pos


def test_state_slot_filled_from_file(tmp_path):
    cfg = load_config(tmp_path)
    kelix = tmp_path / ".kelix"
    kelix.mkdir()
    (kelix / "STATE.md").write_text(
        "# Kelix state\n\n- milestone: v0.2\n- phase: P-SPINE\n",
        encoding="utf-8",
    )
    out, _manifest = assemble_prompt(DEFAULT_TEMPLATE, cfg, state=(kelix / "STATE.md").read_text())
    assert "milestone: v0.2" in out
    assert "P-SPINE" in out
    assert "(no state file" not in out


def test_state_budget_enforced(tmp_path):
    (tmp_path / "kelix.toml").write_text("[memory]\nstate_max_chars = 40\n")
    cfg = load_config(tmp_path)
    out, _manifest = assemble_prompt(DEFAULT_TEMPLATE, cfg, state="s" * 500)
    assert "truncated to 40 chars" in out
    assert "s" * 41 not in out


def test_phase_context_slot_before_episode_digest():
    phase_pos = DEFAULT_TEMPLATE.index("{{PHASE_CONTEXT}}")
    digest_pos = DEFAULT_TEMPLATE.index("{{MEMORY_DIGEST}}")
    assert phase_pos < digest_pos


def test_phase_context_absent_shows_fallback(tmp_path):
    cfg = load_config(tmp_path)
    out, _manifest = assemble_prompt(DEFAULT_TEMPLATE, cfg)
    assert "(no phase decisions)" in out


def test_phase_context_injected_with_banner(tmp_path):
    cfg = load_config(tmp_path)
    context = "## Decisions\n\nUse pytest for all tests.\n"
    out, _manifest = assemble_prompt(DEFAULT_TEMPLATE, cfg, phase_context=context)
    assert PHASE_CONTEXT_BANNER in out
    assert "Use pytest for all tests." in out
    assert "(no phase decisions)" not in out


def test_phase_context_budget_enforced(tmp_path):
    (tmp_path / "kelix.toml").write_text("[memory]\nphase_context_max_chars = 60\n")
    cfg = load_config(tmp_path)
    out, _manifest = assemble_prompt(DEFAULT_TEMPLATE, cfg, phase_context="x" * 500)
    assert "truncated to 60 chars" in out
    assert "x" * 61 not in out


def test_load_phase_context_from_active_phase(tmp_path):
    kelix = tmp_path / ".kelix"
    phase_dir = kelix / "phases" / "P-INTENT"
    phase_dir.mkdir(parents=True)
    (phase_dir / "CONTEXT.md").write_text("Decision: use stdlib only.\n", encoding="utf-8")
    assert load_phase_context(kelix, "P-INTENT") == "Decision: use stdlib only.\n"
    assert load_phase_context(kelix, "P-OTHER") == ""
    assert load_phase_context(kelix, "") == ""


def test_format_phase_context_empty():
    assert format_phase_context("") == ""
    assert format_phase_context("   \n") == ""


def test_init_writes_phases_readme(tmp_path):
    from kelix.cli import cmd_init

    class Args:
        path = str(tmp_path)
        from_spec = ""

    cmd_init(Args())
    readme = tmp_path / ".kelix" / "phases" / "README.md"
    assert readme.is_file()
    text = readme.read_text(encoding="utf-8")
    assert "CONTEXT.md" in text
    assert "phase-id" in text


def test_init_writes_goal_md(tmp_path):
    from kelix.cli import GOAL_TEMPLATE, cmd_init

    class Args:
        path = str(tmp_path)
        from_spec = ""

    cmd_init(Args())
    goal = tmp_path / "GOAL.md"
    assert goal.is_file()
    text = goal.read_text(encoding="utf-8")
    assert text == GOAL_TEMPLATE
    assert "## Non-goals" in text
    assert "## Acceptance" in text


def test_init_does_not_overwrite_existing_goal_md(tmp_path):
    from kelix.cli import cmd_init

    class Args:
        path = str(tmp_path)
        from_spec = ""

    goal = tmp_path / "GOAL.md"
    goal.write_text("custom goal\n", encoding="utf-8")
    cmd_init(Args())
    assert goal.read_text(encoding="utf-8") == "custom goal\n"


def test_init_writes_roadmap_template(tmp_path):
    from kelix.cli import ROADMAP_TEMPLATE, cmd_init

    class Args:
        path = str(tmp_path)
        from_spec = ""

    cmd_init(Args())
    roadmap = tmp_path / ".kelix" / "roadmap.md"
    assert roadmap.is_file()
    text = roadmap.read_text(encoding="utf-8")
    assert text == ROADMAP_TEMPLATE
    assert "## Milestone M1" in text
    assert "REQ-EX1" in text


def test_init_does_not_overwrite_existing_roadmap(tmp_path):
    from kelix.cli import cmd_init

    class Args:
        path = str(tmp_path)
        from_spec = ""

    kelix = tmp_path / ".kelix"
    kelix.mkdir()
    roadmap = kelix / "roadmap.md"
    roadmap.write_text("custom roadmap\n", encoding="utf-8")
    cmd_init(Args())
    assert roadmap.read_text(encoding="utf-8") == "custom roadmap\n"


def test_context_share_controls_total_data_budget(tmp_path):
    (tmp_path / "kelix.toml").write_text(
        """
[memory]
context_share = 0.5
state_max_chars = 100
phase_context_max_chars = 100
digest_max_chars = 1000
project_max_chars = 1000
skills_max_chars = 1000
mailbox_max_chars = 1000
"""
    )
    cfg = load_config(tmp_path)
    caps_total = 100 + 100 + 1000 + 1000 + 1000 + 1000
    budgets = compute_slot_budgets(cfg)
    assert sum(budgets.values()) <= int(0.5 * caps_total) + 6


def test_state_slot_not_starved_at_low_context_share(tmp_path):
    (tmp_path / "kelix.toml").write_text(
        """
[memory]
context_share = 0.05
state_max_chars = 400
phase_context_max_chars = 400
digest_max_chars = 4000
project_max_chars = 4000
skills_max_chars = 4000
mailbox_max_chars = 4000
"""
    )
    cfg = load_config(tmp_path)
    state_text = "milestone: v0.2\nphase: P-CONTEXT\n"
    out, _manifest = assemble_prompt(DEFAULT_TEMPLATE, cfg, state=state_text)
    assert state_text.strip() in out
    assert "truncated" not in out.split("<state>")[1].split("</state>")[0]


def test_relevance_query_from_select_next_ready_task(tmp_path):
    cfg = load_config(tmp_path)
    backlog = tmp_path / cfg.loop.plan_file
    backlog.parent.mkdir(parents=True, exist_ok=True)
    backlog.write_text(
        "- [ ] PC21: context budget split | priority: 79 | status: ready | by: owner\n"
        "  details: allocate context_share across prompt slots\n"
    )
    query = relevance_query_for_task(cfg, tmp_path)
    assert "context budget split" in query
    assert "context_share" in query


def test_assemble_prompt_passes_query_to_episode_selector(tmp_path):
    import json

    (tmp_path / "kelix.toml").write_text(
        """
[memory]
context_share = 1.0
state_max_chars = 1
phase_context_max_chars = 1
digest_max_chars = 80
project_max_chars = 69
skills_max_chars = 69
mailbox_max_chars = 1
"""
    )
    cfg = load_config(tmp_path)
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
    ]
    (ep_dir / "episodes.jsonl").write_text(
        "\n".join(json.dumps(ep) for ep in episodes) + "\n"
    )
    out, manifest = assemble_prompt(
        DEFAULT_TEMPLATE,
        cfg,
        relevance_query="backlog parser waves",
        workdir=tmp_path,
    )
    assert "backlog parser wave computation" in out
    assert "readme unrelated marketing" not in out
    assert any(
        item["slot"] == "episodes"
        and (item.get("score") or 0) > 0
        and "2026-01-01" in item["source"]
        for item in manifest
    )


def test_context_manifest_relevance_beats_recency(tmp_path):
    """REQ-C4: old relevant gotcha beats recent noise; manifest records score."""
    import json

    (tmp_path / "kelix.toml").write_text(
        """
[memory]
context_share = 1.0
state_max_chars = 1
phase_context_max_chars = 1
digest_max_chars = 200
project_max_chars = 69
skills_max_chars = 69
mailbox_max_chars = 1
"""
    )
    cfg = load_config(tmp_path)
    ep_dir = tmp_path / ".kelix" / "memory"
    ep_dir.mkdir(parents=True)
    episodes = [
        {
            "ts": "2026-01-01T00:00:00",
            "rationale": (
                "PC22 — GOTCHA never run pip install -e inside a run worktree"
            ),
            "verified": True,
            "failure": "",
        },
        {
            "ts": "2026-07-02T00:00:00",
            "rationale": "KE1 — readme marketing fluff unrelated",
            "verified": True,
            "failure": "",
        },
        {
            "ts": "2026-07-03T00:00:00",
            "rationale": "KE2 — docs index more unrelated noise",
            "verified": True,
            "failure": "",
        },
    ]
    (ep_dir / "episodes.jsonl").write_text(
        "\n".join(json.dumps(ep) for ep in episodes) + "\n"
    )
    query = "pip install editable worktree venv gotcha"
    out, manifest = assemble_prompt(
        DEFAULT_TEMPLATE,
        cfg,
        relevance_query=query,
        workdir=tmp_path,
    )
    assert "pip install -e" in out
    assert "readme marketing fluff" not in out
    scored = [
        item
        for item in manifest
        if item["slot"] == "episodes" and item.get("score") is not None
    ]
    assert scored
    assert any(item["score"] > 0 for item in scored)
    assert any("2026-01-01" in item["source"] for item in scored)
