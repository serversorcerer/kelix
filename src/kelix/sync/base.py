"""Tracker adapter interface + inbound sanitization (shared by all trackers)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol


class SyncError(Exception):
    pass


@dataclass
class InboundIssue:
    """An issue pulled from a tracker, ready to become a backlog task.

    `title` and `body` are already sanitized. `external_id` is the tracker's
    stable id (e.g. Linear "KAL-123"); `identifier` is the human ref used for
    branch naming.
    """

    external_id: str
    identifier: str
    title: str
    body: str = ""
    priority: int = 80  # owner-authored tracker issues land in the owner band
    state: str = "ready"
    labels: list[str] = field(default_factory=list)


# Patterns that look like attempts to hijack the loop from inside issue text.
_INJECTION_MARKERS = [
    re.compile(r"(?i)ignore (all|any|previous|your) (instructions|rules)"),
    re.compile(r"(?i)disregard (the )?(loop )?(contract|rules)"),
    re.compile(r"(?i)push (directly )?to (main|master)"),
    re.compile(r"(?i)force[- ]push"),
    re.compile(r"(?i)(reveal|print|exfiltrate|leak).{0,20}(secret|token|key|credential)"),
    re.compile(r"(?i)system prompt"),
    re.compile(r"(?i)you are now"),
]


def sanitize_inbound(text: str, max_len: int = 4000) -> str:
    """Neutralize untrusted tracker text so it is safe to embed as data.

    We do not silently drop content (the owner may have legitimately written
    something that trips a marker); we defang formatting that could break the
    backlog line format and we annotate injection-looking spans so a reviewing
    human and the agent both see they are data, not commands.
    """
    if not text:
        return ""
    text = text.replace("\r\n", "\n")
    # Collapse to single spaces for the title-like fields; keep it one logical
    # blob. Pipe and backtick fencing removed so it can't forge task fields or
    # code the agent might be tempted to run.
    text = text.replace("|", "/").replace("`", "'")
    for marker in _INJECTION_MARKERS:
        text = marker.sub(lambda m: f"[flagged-untrusted: {m.group(0)}]", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > max_len:
        text = text[:max_len] + " [...truncated]"
    return text


class TrackerAdapter(Protocol):
    """A tracker adapter. All methods must be non-fatal on failure: log and
    return a benign value; never raise into the loop."""

    name: str

    def fetch_issues(self) -> list[InboundIssue]:
        """Return owner-authored issues to mirror inbound as top-ranked tasks."""
        ...

    def push_status(self, external_id: str, status: str, evidence: str) -> bool:
        """Comment status/verification evidence back on the issue."""
        ...

    def push_pr_link(self, external_id: str, url: str) -> bool:
        """Comment a PR link back on the issue."""
        ...
