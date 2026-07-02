# Security Policy

Kalph runs unattended coding-agent loops with shell access, so we take
security reports seriously. This file is the reporting policy; the full
threat model and mitigations live in [docs/SECURITY.md](docs/SECURITY.md).

## Reporting a vulnerability

**Please do not report security issues in public GitHub issues.**

Report privately via GitHub Security Advisories on this repository:
**Security → Report a vulnerability**
(or https://github.com/kalph-dev/kalph/security/advisories/new).

Include what you can: affected version, reproduction steps, and impact
(e.g. denylist bypass, prompt-injection escape, secret leakage into
artifacts).

We aim to **acknowledge reports within 72 hours** and will keep you updated
as we triage, fix, and disclose.

## Supported versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

## Scope notes

Especially interesting reports include anything that lets repo or tracker
content act as instructions, bypasses the command denylist, pushes to a
protected branch, or leaks secrets into transcripts, commits, or PR bodies.
See [docs/SECURITY.md](docs/SECURITY.md) for the complete threat model.
