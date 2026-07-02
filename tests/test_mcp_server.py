"""MCP server protocol tests (no real agent; drives the stdio JSON-RPC surface)."""

import io
import json

from conftest import make_repo, write_mock_script

from kalph.mcp_server import MCPServer, serve


def test_initialize_and_tools_list(tmp_path):
    server = MCPServer(tmp_path)
    init = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert init["result"]["serverInfo"]["name"] == "kalph"
    listing = server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = {t["name"] for t in listing["result"]["tools"]}
    assert names == {"kalph_run", "kalph_status", "kalph_memory", "kalph_stop"}


def test_notification_gets_no_response(tmp_path):
    server = MCPServer(tmp_path)
    assert server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_unknown_method_errors(tmp_path):
    server = MCPServer(tmp_path)
    resp = server.handle({"jsonrpc": "2.0", "id": 9, "method": "bogus"})
    assert resp["error"]["code"] == -32601


def test_tools_call_stop_sets_kill_switch(tmp_path):
    repo = make_repo(tmp_path / "repo")
    server = MCPServer(repo)
    resp = server.handle({
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": "kalph_stop", "arguments": {}},
    })
    assert resp["result"]["isError"] is False
    assert (repo / ".kalph" / "STOP").exists()


def test_tools_call_run_via_mock(tmp_path):
    repo = make_repo(tmp_path / "repo")
    write_mock_script(
        repo / "mockdir",
        "001.sh",
        'echo "RATIONALE: T1 — x"\necho w >> w.txt\ngit add -A && git commit -q -m T1\n',
    )
    (repo / "kalph.toml").write_text(
        '[agent]\nadapter = "mock"\nmock_dir = "mockdir"\n[git]\nisolation = "none"\n'
    )
    server = MCPServer(repo)
    resp = server.handle({
        "jsonrpc": "2.0", "id": 4, "method": "tools/call",
        "params": {"name": "kalph_run", "arguments": {"max_iterations": 2}},
    })
    text = resp["result"]["content"][0]["text"]
    assert "completed" in text


def test_serve_reads_stdio(tmp_path):
    repo = make_repo(tmp_path / "repo")
    inp = io.StringIO(
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"}) + "\n"
        + json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}) + "\n"
    )
    out = io.StringIO()
    serve(repo, stdin=inp, stdout=out)
    lines = [json.loads(x) for x in out.getvalue().splitlines()]
    assert lines[0]["result"]["protocolVersion"]
    assert len(lines[1]["result"]["tools"]) == 4
