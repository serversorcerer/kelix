"""Parse `.kelix/roadmap.md` — milestones, phases, and REQ coverage."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

MILESTONE_LINE = re.compile(r"^## Milestone (.+?) — (.+)$")
PHASE_LINE = re.compile(r"^### Phase (\S+) — (.+)$")
REQ_LINE = re.compile(r"^- (REQ-\S+): (.*)$")
OUTCOME_LINE = re.compile(r"^Outcome: (.*)$")


@dataclass
class Milestone:
    id: str
    title: str


@dataclass
class Phase:
    id: str
    title: str
    outcome: str = ""
    milestone_id: str = ""


@dataclass
class Req:
    id: str
    text: str
    phase_id: str = ""


@dataclass
class Roadmap:
    milestones: list[Milestone] = field(default_factory=list)
    phases: list[Phase] = field(default_factory=list)
    reqs: list[Req] = field(default_factory=list)

    def reqs_for(self, phase_id: str) -> list[Req]:
        """Return all REQs belonging to *phase_id*."""
        return [req for req in self.reqs if req.phase_id == phase_id]


def parse_roadmap(text: str) -> Roadmap:
    """Parse roadmap markdown. Prose between sections is ignored."""
    roadmap = Roadmap()
    current_milestone_id = ""
    current_phase_id = ""
    pending_outcome = False

    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue

        milestone_match = MILESTONE_LINE.match(line)
        if milestone_match:
            current_milestone_id = milestone_match.group(1).strip()
            roadmap.milestones.append(
                Milestone(id=current_milestone_id, title=milestone_match.group(2).strip())
            )
            current_phase_id = ""
            pending_outcome = False
            continue

        phase_match = PHASE_LINE.match(line)
        if phase_match:
            current_phase_id = phase_match.group(1).strip()
            roadmap.phases.append(
                Phase(
                    id=current_phase_id,
                    title=phase_match.group(2).strip(),
                    milestone_id=current_milestone_id,
                )
            )
            pending_outcome = True
            continue

        if pending_outcome and current_phase_id:
            outcome_match = OUTCOME_LINE.match(line)
            if outcome_match:
                for phase in reversed(roadmap.phases):
                    if phase.id == current_phase_id:
                        phase.outcome = outcome_match.group(1).strip()
                        break
                pending_outcome = False
                continue

        req_match = REQ_LINE.match(line)
        if req_match and current_phase_id:
            pending_outcome = False
            roadmap.reqs.append(
                Req(
                    id=req_match.group(1),
                    text=req_match.group(2).strip(),
                    phase_id=current_phase_id,
                )
            )

    return roadmap


def load_roadmap(kelix_dir: Path | str) -> Roadmap | None:
    """Load roadmap.md from *kelix_dir*. Missing file returns None."""
    path = Path(kelix_dir) / "roadmap.md"
    if not path.is_file():
        return None
    return parse_roadmap(path.read_text(encoding="utf-8"))
