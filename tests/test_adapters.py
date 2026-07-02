import stat

import pytest

from kelix import COMPLETION_SENTINEL
from kelix.adapters import AdapterError, CmdAdapter, MockAdapter, make_adapter
from kelix.config import load_config


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
