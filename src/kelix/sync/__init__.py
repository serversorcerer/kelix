"""Issue-tracker sync.

`.kelix/backlog.md` is always the loop's single source of truth. A sync adapter
optionally mirrors it to an external tracker so the owner can author and
monitor from their tool of choice. Design rules (mission):

- The loop runs fine with sync disabled or the tracker unreachable. Sync
  failures are logged and skipped, never fatal.
- Inbound issue text is UNTRUSTED data: it is sanitized on the way in and only
  ever becomes a task title/notes, never instructions that can change the loop
  contract.
- The adapter interface is tracker-agnostic; Linear is the reference
  implementation, GitHub Issues (etc.) can be added without touching the loop.
"""

from .base import InboundIssue, SyncError, TrackerAdapter, sanitize_inbound
from .linear import LinearAdapter

__all__ = [
    "TrackerAdapter",
    "InboundIssue",
    "SyncError",
    "sanitize_inbound",
    "LinearAdapter",
    "make_tracker",
]


def make_tracker(cfg):
    """Build the configured tracker adapter, or None when sync is disabled."""
    provider = cfg.tracker.provider
    if not provider:
        return None
    if provider == "linear":
        return LinearAdapter(team=cfg.tracker.team)
    raise SyncError(f"unknown tracker provider {provider!r}")
