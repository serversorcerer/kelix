import pytest

from kelix.adapters import CmdAdapter, make_adapter
from kelix.config import ADAPTER_PRESET_COMMANDS, Config, ConfigError, load_config


def test_defaults_when_no_file(tmp_path):
    cfg = load_config(tmp_path)
    assert cfg.agent.adapter == "kiro"
    assert cfg.loop.max_iterations == 25
    assert cfg.loop.circuit_breaker_threshold == 3
    assert cfg.loop.diagnose_transcript_chars == 50000
    assert cfg.loop.diagnose_default_runs == 3
    assert cfg.git.isolation == "worktree"
    assert cfg.autonomy.level == "normal"
    assert cfg.security.scrub_transcripts is True
    assert cfg.memory.context_share == 0.5
    assert cfg.memory.distill_skills is True
    assert cfg.kelix_dir == tmp_path.resolve() / ".kelix"


def test_loads_from_kelix_dir(tmp_path):
    (tmp_path / ".kelix").mkdir()
    (tmp_path / ".kelix" / "kelix.toml").write_text(
        """
[agent]
adapter = "mock"
mock_dir = "fixtures/mock"

[loop]
max_iterations = 5

[verify]
commands = ["pytest -q"]
"""
    )
    cfg = load_config(tmp_path)
    assert cfg.agent.adapter == "mock"
    assert cfg.loop.max_iterations == 5
    assert cfg.verify.commands == ["pytest -q"]


def test_root_kelix_toml_is_fallback(tmp_path):
    (tmp_path / "kelix.toml").write_text('[loop]\nmax_iterations = 2\n')
    assert load_config(tmp_path).loop.max_iterations == 2


def test_unknown_key_rejected(tmp_path):
    (tmp_path / "kelix.toml").write_text('[loop]\nmax_iters = 2\n')
    with pytest.raises(ConfigError, match="unknown key"):
        load_config(tmp_path)


def test_wrong_type_rejected(tmp_path):
    (tmp_path / "kelix.toml").write_text('[loop]\nmax_iterations = "lots"\n')
    with pytest.raises(ConfigError, match="must be int"):
        load_config(tmp_path)


def test_cmd_adapter_requires_command(tmp_path):
    (tmp_path / "kelix.toml").write_text('[agent]\nadapter = "cmd"\n')
    with pytest.raises(ConfigError, match="command is required"):
        load_config(tmp_path)


def test_bad_adapter_rejected(tmp_path):
    (tmp_path / "kelix.toml").write_text('[agent]\nadapter = "gpt"\n')
    with pytest.raises(ConfigError, match="unknown agent adapter"):
        load_config(tmp_path)


def test_default_config_is_safe():
    cfg = Config()
    assert cfg.loop.max_iterations <= 25
    assert cfg.git.isolation == "worktree"
    assert cfg.tracker.provider == ""
    assert cfg.memory.context_share == 0.5


def test_context_share_out_of_range_rejected(tmp_path):
    (tmp_path / "kelix.toml").write_text("[memory]\ncontext_share = 1.5\n")
    with pytest.raises(ConfigError, match="context_share"):
        load_config(tmp_path)


@pytest.mark.parametrize("preset", ADAPTER_PRESET_COMMANDS)
def test_named_adapter_preset_loads(tmp_path, preset):
    (tmp_path / "kelix.toml").write_text(f'[agent]\nadapter = "{preset}"\n')
    cfg = load_config(tmp_path)
    assert cfg.agent.adapter == preset
    assert cfg.agent.command == ADAPTER_PRESET_COMMANDS[preset]


@pytest.mark.parametrize("preset", ADAPTER_PRESET_COMMANDS)
def test_named_adapter_preset_resolves_to_cmd(tmp_path, preset):
    (tmp_path / "kelix.toml").write_text(f'[agent]\nadapter = "{preset}"\n')
    cfg = load_config(tmp_path)
    assert isinstance(make_adapter(cfg), CmdAdapter)


def test_named_adapter_preset_command_override(tmp_path):
    (tmp_path / "kelix.toml").write_text(
        '[agent]\nadapter = "claude"\ncommand = "echo {prompt}"\n'
    )
    cfg = load_config(tmp_path)
    assert cfg.agent.command == "echo {prompt}"


def test_diagnose_config_overrides(tmp_path):
    (tmp_path / "kelix.toml").write_text(
        "[loop]\n"
        "diagnose_transcript_chars = 12000\n"
        "diagnose_default_runs = 5\n"
    )
    cfg = load_config(tmp_path)
    assert cfg.loop.diagnose_transcript_chars == 12000
    assert cfg.loop.diagnose_default_runs == 5
