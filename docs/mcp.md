# The Kalph MCP server

`kalph mcp` serves Kalph as an [MCP](https://modelcontextprotocol.io) server
so any MCP-capable agent — Kiro first — can drive the loop by tool call:
start a run, check status, inspect memory, hit the kill switch.

The implementation (`src/kalph/mcp_server.py`) is deliberately
dependency-free: a minimal, auditable JSON-RPC 2.0 loop over
**newline-delimited JSON on stdio**, implementing exactly the subset of MCP
needed here — `initialize`, `tools/list`, and `tools/call` (protocol version
`2024-11-05`). It serves until stdin reaches EOF; malformed lines are ignored;
notifications get no response.

```bash
kalph mcp                 # serve the current directory's repo
kalph mcp --path DIR      # serve another repo
```

## Registering with Kiro CLI

```bash
kiro-cli mcp add --name kalph --command "kalph mcp" --scope workspace
```

After that, a Kiro session in the workspace can call the four tools below.

## The tools

All four tools return a single text content block; errors are reported as a
text result with `isError: true` rather than a protocol failure.

### `kalph_run`

Start a Kalph loop run against the repository. **Runs synchronously** — the
tool call does not return until the run finishes — and returns the run status
and a per-iteration summary (rationale and outcome per iteration, plus the
diagnosis path if the circuit breaker tripped). Use `max_iterations` to bound
cost.

```json
{
  "type": "object",
  "properties": {
    "max_iterations": {"type": "integer", "minimum": 1},
    "role": {"type": "string", "description": "optional role text"}
  }
}
```

### `kalph_status`

Show current run/fleet status derived from coordination files: task claims,
recent runs, mailbox notes, and the kill switch. Same output as
`kalph status`. Takes no arguments.

```json
{"type": "object", "properties": {}}
```

### `kalph_memory`

Inspect Kalph's memory: the project memory file, the recent-episode digest,
and the earned-skills digest (see
[memory-and-skills.md](memory-and-skills.md)).

```json
{
  "type": "object",
  "properties": {
    "episodes": {"type": "integer", "minimum": 0, "default": 10}
  }
}
```

### `kalph_stop`

Set the kill switch (`.kalph/STOP`) so active and future runs halt before
their next iteration. Takes no arguments. Remove the file to allow runs again.

```json
{"type": "object", "properties": {}}
```

## Trying it by hand

The wire format is plain enough to poke at without a client — one JSON-RPC
request per line on stdin:

```bash
printf '%s\n%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  | kalph mcp
```

A tool call looks like:

```json
{"jsonrpc":"2.0","id":3,"method":"tools/call",
 "params":{"name":"kalph_run","arguments":{"max_iterations":5}}}
```
