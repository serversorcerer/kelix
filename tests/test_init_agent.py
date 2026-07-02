"""Tests for kelix init --agent wiring (REQ-A3)."""

from __future__ import annotations

import tomllib

from kelix.cli import cmd_init, render_config_template
from kelix.config import load_config


class InitArgs:
    path = "."
    from_spec = ""
    agent = ""


def test_render_config_template_named_preset():
    text = render_config_template("claude")
    assert 'adapter = "claude"' in text
    assert "command =" not in text


def test_render_config_template_cmd_includes_command():
    text = render_config_template("cmd")
    assert 'adapter = "cmd"' in text
    assert 'command = "your-cli {prompt}"' in text


def test_init_non_tty_requires_agent(tmp_path, capsys):
    args = InitArgs()
    args.path = str(tmp_path)

    code = cmd_init(args, is_tty=False)
    captured = capsys.readouterr()

    assert code == 2
    assert "--agent" in captured.err
    assert not (tmp_path / ".kelix" / "kelix.toml").exists()


def test_init_agent_flag_writes_adapter(tmp_path):
    args = InitArgs()
    args.path = str(tmp_path)
    args.agent = "cursor"

    assert cmd_init(args, is_tty=False) == 0

    raw = tomllib.loads((tmp_path / ".kelix" / "kelix.toml").read_text(encoding="utf-8"))
    assert raw["agent"]["adapter"] == "cursor"
    cfg = load_config(tmp_path)
    assert cfg.agent.adapter == "cursor"
    assert "cursor-agent" in cfg.agent.command


def test_init_agent_cmd_writes_command_field(tmp_path):
    args = InitArgs()
    args.path = str(tmp_path)
    args.agent = "cmd"

    assert cmd_init(args, is_tty=False) == 0

    text = (tmp_path / ".kelix" / "kelix.toml").read_text(encoding="utf-8")
    assert 'adapter = "cmd"' in text
    assert 'command = "your-cli {prompt}"' in text
    cfg = load_config(tmp_path)
    assert cfg.agent.adapter == "cmd"
    assert cfg.agent.command == "your-cli {prompt}"


def test_init_tty_prompt_selects_agent(tmp_path):
    args = InitArgs()
    args.path = str(tmp_path)
    args.agent = ""
    inputs = iter(["3"])

    code = cmd_init(
        args,
        is_tty=True,
        input_fn=lambda _prompt: next(inputs),
        print_fn=lambda _msg: None,
    )

    assert code == 0
    raw = tomllib.loads((tmp_path / ".kelix" / "kelix.toml").read_text(encoding="utf-8"))
    assert raw["agent"]["adapter"] == "codex"


def test_init_tty_empty_input_defaults_kiro(tmp_path):
    args = InitArgs()
    args.path = str(tmp_path)
    args.agent = ""

    code = cmd_init(
        args,
        is_tty=True,
        input_fn=lambda _prompt: "",
        print_fn=lambda _msg: None,
    )

    assert code == 0
    raw = tomllib.loads((tmp_path / ".kelix" / "kelix.toml").read_text(encoding="utf-8"))
    assert raw["agent"]["adapter"] == "kiro"


def test_init_skips_agent_when_kelix_toml_exists(tmp_path):
    kelix = tmp_path / ".kelix"
    kelix.mkdir()
    existing = kelix / "kelix.toml"
    existing.write_text('[agent]\nadapter = "mock"\n', encoding="utf-8")

    args = InitArgs()
    args.path = str(tmp_path)
    args.agent = ""

    assert cmd_init(args, is_tty=False) == 0
    assert existing.read_text(encoding="utf-8") == '[agent]\nadapter = "mock"\n'
