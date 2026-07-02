"""Security utilities: transcript scrubbing and the command policy engine.

Threat model (docs/SECURITY.md): an unattended agent with shell access working
on repo content that may contain injected instructions. The runner-side
mitigations live here so they hold regardless of which agent backend runs.
"""

from __future__ import annotations

import re

# --- secret scrubbing --------------------------------------------------------

# Known token shapes. Deliberately specific: false positives in transcripts are
# cheap, but silently leaking a credential into a committed log is not.
_SECRET_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("github-token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b")),
    ("github-pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("kiro-api-key", re.compile(r"\bksk_[A-Za-z0-9]{8,}\b")),
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("openai-key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("anthropic-key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b")),
    ("linear-key", re.compile(r"\blin_api_[A-Za-z0-9]{20,}\b")),
    (
        "private-key-block",
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"
        ),
    ),
    ("generic-bearer", re.compile(r"(?i)\b(authorization:\s*bearer)\s+[A-Za-z0-9._~+/-]{16,}=*")),
]


def scrub(text: str) -> str:
    """Replace anything that looks like a credential with a labeled marker."""
    for label, pattern in _SECRET_PATTERNS:
        text = pattern.sub(f"[REDACTED:{label}]", text)
    return text


def contains_secret(text: str) -> bool:
    return any(p.search(text) for _, p in _SECRET_PATTERNS)


# --- command policy ----------------------------------------------------------

# Dangerous-by-default patterns, matched against whole shell command strings.
# These guard the *runner's own* subprocess surface and are exported to the
# Kiro agent config (toolsSettings.shell.deniedCommands) so the same policy is
# enforced inside the agent too.
DEFAULT_DENY: list[str] = [
    r"curl[^|;&]*\|\s*(ba)?sh",          # curl | sh
    r"wget[^|;&]*\|\s*(ba)?sh",
    r"git\s+push\s+.*--force",           # force push
    r"git\s+push\s+[^ ]*\s+(main|master)\b",  # direct push to protected
    r"rm\s+-[a-z]*rf?\s+(/|~|\$HOME)(\s|$)",  # rm -rf / or ~
    r"npm\s+publish", r"cargo\s+publish", r"twine\s+upload", r"gem\s+push",
    r"cat\s+.*(\.aws/credentials|\.ssh/id_|\.netrc|\.npmrc)",
    r"(^|[;&|]\s*)(sudo|doas)\s",
    r"chmod\s+.*777\s+/",
    r"git\s+config\s+.*credential",
    r"base64\s+.*(\.aws|\.ssh|\.netrc)",
]


class CommandPolicy:
    """Allowlist/denylist for shell commands.

    Deny always wins. If `allow_only` is non-empty, commands must additionally
    start with one of those prefixes (allowlist mode).
    """

    def __init__(self, deny_extra: list[str] | None = None, allow_only: list[str] | None = None):
        self._deny = [re.compile(p) for p in DEFAULT_DENY + list(deny_extra or [])]
        self._allow_only = list(allow_only or [])

    def check(self, command: str) -> tuple[bool, str]:
        """Returns (allowed, reason-if-denied)."""
        for pattern in self._deny:
            if pattern.search(command):
                return False, f"denied by policy pattern: {pattern.pattern}"
        if self._allow_only:
            stripped = command.strip()
            if not any(stripped.startswith(prefix) for prefix in self._allow_only):
                return False, "not in allowlist (allow_only mode)"
        return True, ""
