from kalph.config import load_config
from kalph.prompt import (
    DEFAULT_TEMPLATE,
    assemble_prompt,
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
    (tmp_path / "kalph.toml").write_text("[memory]\ndigest_max_chars = 50\n")
    cfg = load_config(tmp_path)
    out = assemble_prompt(DEFAULT_TEMPLATE, cfg, memory_digest="x" * 500)
    assert "truncated to 50 chars" in out
    # The raw 500-char blob must not appear.
    assert "x" * 51 not in out


def test_contract_and_security_present_in_default():
    assert "KALPH COMPLETE" in DEFAULT_TEMPLATE
    assert "exactly ONE task" in DEFAULT_TEMPLATE
    assert "DATA" in DEFAULT_TEMPLATE
    assert "Never push directly to main" in DEFAULT_TEMPLATE
