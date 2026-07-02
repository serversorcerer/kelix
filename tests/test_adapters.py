import os
import stat

import pytest
from conftest import make_repo

from kelix import COMPLETION_SENTINEL
from kelix.adapters import AdapterError, CmdAdapter, MockAdapter, make_adapter
from kelix.config import ADAPTER_PRESET_COMMANDS, load_config
from kelix.loop import Runner


def _write_script(path, body):
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def test_cmd_adapter_stdin_mode(tmp_path):
    (tmp_path / "kelix.toml").write_text('[agent]\nadapter = "cmd"\ncommand = "cat"\n')
    cfg = load_config(tmp_path)
    result = CmdAdapter(cfg).run("hello prompt", tmp_path)
    assert result.ok
    assert result.output == "hello prompt"


def test_cmd_adapter_prompt_file_token(tmp_path):
    (tmp_path / "kelix.toml").write_text(
        '[agent]\nadapter = "cmd"\ncommand = "cat {prompt_file}"\n'
    )
    cfg = load_config(tmp_path)
    result = CmdAdapter(cfg).run("from a file", tmp_path)
    assert result.ok
    assert result.output == "from a file"


def test_cmd_adapter_prompt_token(tmp_path):
    (tmp_path / "kelix.toml").write_text(
        '[agent]\nadapter = "cmd"\ncommand = "echo {prompt}"\n'
    )
    cfg = load_config(tmp_path)
    result = CmdAdapter(cfg).run("inline", tmp_path)
    assert result.ok
    assert result.output.strip() == "inline"


def test_cmd_adapter_timeout(tmp_path):
    (tmp_path / "kelix.toml").write_text(
        '[agent]\nadapter = "cmd"\ncommand = "sleep 5"\ntimeout_seconds = 1\n'
    )
    cfg = load_config(tmp_path)
    result = CmdAdapter(cfg).run("x", tmp_path)
    assert result.timed_out
    assert not result.ok


def test_cmd_adapter_missing_binary(tmp_path):
    (tmp_path / "kelix.toml").write_text(
        '[agent]\nadapter = "cmd"\ncommand = "kelix-no-such-binary-xyz"\n'
    )
    cfg = load_config(tmp_path)
    with pytest.raises(AdapterError, match="not found"):
        CmdAdapter(cfg).run("x", tmp_path)


def test_mock_adapter_plays_scripts_then_sentinel(tmp_path):
    mock = tmp_path / "mock"
    mock.mkdir()
    _write_script(mock / "001-first.sh", 'echo "did task one"')
    _write_script(mock / "002-second.sh", 'echo "did task two"')
    (tmp_path / "kelix.toml").write_text(
        '[agent]\nadapter = "mock"\nmock_dir = "mock"\n'
    )
    cfg = load_config(tmp_path)
    adapter = MockAdapter(cfg)
    assert adapter.run("p", tmp_path).output.strip() == "did task one"
    assert adapter.run("p", tmp_path).output.strip() == "did task two"
    assert COMPLETION_SENTINEL in adapter.run("p", tmp_path).output


def test_mock_scripts_get_prompt_on_stdin_and_cwd(tmp_path):
    mock = tmp_path / "mock"
    mock.mkdir()
    _write_script(mock / "001.sh", "cat > received.txt; pwd")
    (tmp_path / "kelix.toml").write_text(
        '[agent]\nadapter = "mock"\nmock_dir = "mock"\n'
    )
    cfg = load_config(tmp_path)
    workdir = tmp_path / "work"
    workdir.mkdir()
    result = MockAdapter(cfg).run("the prompt", workdir)
    assert result.ok
    assert (workdir / "received.txt").read_text() == "the prompt"
    assert result.output.strip().endswith("work")


def test_make_adapter_dispatch(tmp_path):
    (tmp_path / "mock").mkdir()
    (tmp_path / "kelix.toml").write_text(
        '[agent]\nadapter = "mock"\nmock_dir = "mock"\n'
    )
    cfg = load_config(tmp_path)
    assert isinstance(make_adapter(cfg), MockAdapter)


def test_cmd_adapter_inactivity_timeout(tmp_path):
    script = tmp_path / "idle.py"
    script.write_text("import time\nprint('started', flush=True)\ntime.sleep(10)\n")
    (tmp_path / "kelix.toml").write_text(
        "[agent]\nadapter = \"cmd\"\n"
        f'command = "python3 {script}"\n'
        "timeout_seconds = 30\n"
        "inactivity_timeout_seconds = 1\n"
    )
    cfg = load_config(tmp_path)
    result = CmdAdapter(cfg).run("x", tmp_path)
    assert result.timed_out
    assert not result.ok
    assert "started" in result.output


def test_claude_preset_run_integration(tmp_path, monkeypatch):
    """KE13: claude preset resolves to CmdAdapter and runs one verified iteration."""
    repo = make_repo(tmp_path / "fixture")
    (repo / ".kelix" / "backlog.md").write_text(
        "# Backlog\n\n"
        "- [ ] C1: create artifact | priority: 90 | status: ready | by: owner\n"
        "  details: write artifact.txt; assert file exists in tests/test_fixture.py\n"
    )
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "claude"
    _write_script(
        stub,
        'echo "RATIONALE: C1 — claude preset stub"\n'
        'echo "stub" > artifact.txt\n'
        "git add artifact.txt && git commit -q -m 'C1: artifact'\n",
    )
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))

    (repo / "kelix.toml").write_text(
        '[agent]\nadapter = "claude"\n'
        '[verify]\ncommands = ["echo verified"]\n'
        '[git]\nisolation = "none"\n'
    )
    cfg = load_config(repo)
    assert cfg.agent.command == ADAPTER_PRESET_COMMANDS["claude"]
    assert isinstance(make_adapter(cfg), CmdAdapter)

    result = Runner(cfg).run(max_iterations=1, log=lambda *_: None)

    assert len(result.iterations) == 1
    assert result.iterations[0].verified
    assert result.iterations[0].made_progress
    assert (repo / "artifact.txt").read_text() == "stub\n"


def test_cmd_adapter_chatty_script_survives_inactivity_window(tmp_path):
    script = tmp_path / "chatty.py"
    script.write_text(
        "import time\n"
        "for i in range(6):\n"
        "    print(f'tick {i}', flush=True)\n"
        "    time.sleep(0.3)\n"
    )
    (tmp_path / "kelix.toml").write_text(
        "[agent]\nadapter = \"cmd\"\n"
        f'command = "python3 {script}"\n'
        "timeout_seconds = 30\n"
        "inactivity_timeout_seconds = 2\n"
    )
    cfg = load_config(tmp_path)
    result = CmdAdapter(cfg).run("x", tmp_path)
    assert result.ok
    assert not result.timed_out
    assert "tick 5" in result.output
