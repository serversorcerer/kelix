from kelix.config import load_config
from kelix.prompt import (
    DEFAULT_TEMPLATE,
    PHASE_CONTEXT_BANNER,
    assemble_prompt,
    format_phase_context,
    load_phase_context,
    load_template,
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
    out = assemble_prompt(DEFAULT_TEMPLATE, cfg)
    assert "{{" not in out
    assert "(no state file — flat-backlog mode)" in out
    assert "(no episodes yet)" in out
    assert "(no skills yet)" in out
    assert "solo builder" in out


def test_slots_filled_with_data(tmp_path):
    cfg = load_config(tmp_path)
    out = assemble_prompt(
        DEFAULT_TEMPLATE, cfg, memory_digest="ep1 ok", skills="skill-a", role="Role: verifier."
    )
    assert "ep1 ok" in out
    assert "skill-a" in out
    assert "Role: verifier." in out


def test_digest_budget_enforced(tmp_path):
    (tmp_path / "kelix.toml").write_text("[memory]\ndigest_max_chars = 50\n")
    cfg = load_config(tmp_path)
    out = assemble_prompt(DEFAULT_TEMPLATE, cfg, memory_digest="x" * 500)
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
    out = assemble_prompt(DEFAULT_TEMPLATE, cfg, state=(kelix / "STATE.md").read_text())
    assert "milestone: v0.2" in out
    assert "P-SPINE" in out
    assert "(no state file" not in out


def test_state_budget_enforced(tmp_path):
    (tmp_path / "kelix.toml").write_text("[memory]\nstate_max_chars = 40\n")
    cfg = load_config(tmp_path)
    out = assemble_prompt(DEFAULT_TEMPLATE, cfg, state="s" * 500)
    assert "truncated to 40 chars" in out
    assert "s" * 41 not in out


def test_phase_context_slot_before_episode_digest():
    phase_pos = DEFAULT_TEMPLATE.index("{{PHASE_CONTEXT}}")
    digest_pos = DEFAULT_TEMPLATE.index("{{MEMORY_DIGEST}}")
    assert phase_pos < digest_pos


def test_phase_context_absent_shows_fallback(tmp_path):
    cfg = load_config(tmp_path)
    out = assemble_prompt(DEFAULT_TEMPLATE, cfg)
    assert "(no phase decisions)" in out


def test_phase_context_injected_with_banner(tmp_path):
    cfg = load_config(tmp_path)
    context = "## Decisions\n\nUse pytest for all tests.\n"
    out = assemble_prompt(DEFAULT_TEMPLATE, cfg, phase_context=context)
    assert PHASE_CONTEXT_BANNER in out
    assert "Use pytest for all tests." in out
    assert "(no phase decisions)" not in out


def test_phase_context_budget_enforced(tmp_path):
    (tmp_path / "kelix.toml").write_text("[memory]\nphase_context_max_chars = 60\n")
    cfg = load_config(tmp_path)
    out = assemble_prompt(DEFAULT_TEMPLATE, cfg, phase_context="x" * 500)
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
