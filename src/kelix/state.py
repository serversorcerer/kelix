"""Read and write `.kelix/STATE.md` — the runner-maintained navigation spine."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

STATE_FILE = "STATE.md"
H1 = "# Kelix state"

FIELD_LINE = re.compile(r"^- (\w+):(?: (.*))?$")
BLOCKER_LINE = re.compile(r"^  - (.+)$")
INT_FIELDS = frozenset({"done", "total"})


@dataclass
class State:
    milestone: str = ""
    phase: str = ""
    current_task: str = ""
    last_task: str = ""
    last_verified_commit: str = ""
    blockers: list[str] = field(default_factory=list)
    done: int = 0
    total: int = 0


def _parse_state_text(text: str) -> State:
    state = State()
    in_blockers = False

    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.startswith(H1):
            continue

        blocker_match = BLOCKER_LINE.match(line)
        if in_blockers and blocker_match:
            value = blocker_match.group(1).strip()
            if value and value != "(none)":
                state.blockers.append(value)
            continue

        field_match = FIELD_LINE.match(line)
        if not field_match:
            in_blockers = False
            continue

        key, value = field_match.group(1), (field_match.group(2) or "").strip()
        if key == "blockers":
            in_blockers = True
            state.blockers = []
            continue

        in_blockers = False
        if key not in INT_FIELDS and not hasattr(state, key):
            continue
        if key in INT_FIELDS:
            try:
                setattr(state, key, int(value))
            except ValueError:
                continue
        else:
            setattr(state, key, value)

    return state


def load_state(kelix_dir: Path | str) -> State | None:
    """Load STATE.md from *kelix_dir*. Missing file returns None."""
    path = Path(kelix_dir) / STATE_FILE
    if not path.is_file():
        return None
    return _parse_state_text(path.read_text(encoding="utf-8"))


def write_state(kelix_dir: Path | str, state: State) -> Path:
    """Write STATE.md to *kelix_dir* using the fixed schema. Returns the path."""
    path = Path(kelix_dir) / STATE_FILE
    lines = [
        H1,
        "",
        f"- milestone: {state.milestone}",
        f"- phase: {state.phase}",
        f"- current_task: {state.current_task}",
        f"- last_task: {state.last_task}",
        f"- last_verified_commit: {state.last_verified_commit}",
        f"- done: {state.done}",
        f"- total: {state.total}",
        "- blockers:",
    ]
    if state.blockers:
        lines.extend(f"  - {blocker}" for blocker in state.blockers)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
