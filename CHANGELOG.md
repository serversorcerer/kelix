# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Nothing yet.

## [0.1.0] - 2026-07-02

### Added

- **Core loop** (`kelix run`): fresh stateless agent per iteration against a
  static prompt, with git worktree isolation, per-iteration auto-checkpoints,
  a verification gate that re-runs your configured commands before a task
  counts as done, a same-failure circuit breaker, and a `kelix stop` kill
  switch.
- **Layered memory**: project, episodic, and skills memory injected into each
  iteration as budgeted data; skills use the agentskills.io format.
- **Backlog and prioritization**: `.kelix/backlog.md` task queue, legible
  prioritization with a one-line `RATIONALE:` per pick, and
  branch-per-task work on `kelix/*` run branches (owner merges when satisfied;
  automated PR opening removed KV3).
- **Tracker sync**: Linear integration with inbound sanitization of
  untrusted tracker text.
- **Kiro integration**: steering files, a custom `kelix` agent, spec import
  (`kelix init --from-spec`), and an MCP server (`kelix mcp`) so Kiro can
  drive Kelix by tool call.
- **Fleet mode** (`kelix fleet`): multiple role-specialized loops (builders,
  verifier, scribe) coordinating only through files — atomic task claims, a
  mailbox, and shared skills.
- **Security**: command denylist with safe defaults (blocks `curl | sh`,
  force-push and pushes to main/master, package publish, credential reads),
  secret scrubbing of transcripts and outbound comments, and
  prompt-injection defenses treating repo/tracker text as data, never
  instructions.
- **CI**: test suite (mock agent, no API keys) and lint run on every commit,
  including denylist regression and prompt-injection drill tests.

[Unreleased]: https://github.com/serversorcerer/kelix/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/serversorcerer/kelix/releases/tag/v0.1.0
