"""Kelix: the Ralph loop, rebuilt for Kiro.

Stateless agent loop with externalized state. The four invariants
(docs/research/ralph-invariants.md): static prompt, fresh context per
iteration, deterministic stop sentinel, state in files and git.
"""

__version__ = "0.1.0"

COMPLETION_SENTINEL = "KELIX COMPLETE"
