from pathlib import Path

from kalph.roadmap import Milestone, Req, load_roadmap, parse_roadmap

REAL_ROADMAP = Path(__file__).resolve().parents[1] / ".kalph" / "roadmap.md"


def test_parse_real_roadmap():
    text = REAL_ROADMAP.read_text(encoding="utf-8")
    roadmap = parse_roadmap(text)

    assert len(roadmap.milestones) >= 2
    assert roadmap.milestones[0].id == "v0.2"
    assert "Planning Core" in roadmap.milestones[0].title

    spine = next(p for p in roadmap.phases if p.id == "P-SPINE")
    assert spine.title == "the state spine"
    assert spine.milestone_id == "v0.2"
    assert "every iteration starts" in spine.outcome

    spine_reqs = roadmap.reqs_for("P-SPINE")
    assert {r.id for r in spine_reqs} == {"REQ-S1", "REQ-S2", "REQ-S3"}
    assert all(r.phase_id == "P-SPINE" for r in spine_reqs)

    intent_reqs = roadmap.reqs_for("P-INTENT")
    assert {r.id for r in intent_reqs} == {"REQ-I1", "REQ-I2", "REQ-I3"}


def test_load_real_roadmap():
    root = Path(__file__).resolve().parents[1]
    loaded = load_roadmap(root / ".kalph")
    assert loaded is not None
    assert any(m.id == "v0.3" for m in loaded.milestones)


def test_multiple_milestones():
    text = """\
# Roadmap

Some intro prose.

## Milestone m1 — First

### Phase P-A — alpha

Outcome: build alpha.

- REQ-A1: do alpha

## Milestone m2 — Second

Prose between milestones.

### Phase P-B — beta

Outcome: build beta.

- REQ-B1: do beta
- REQ-B2: verify beta
"""
    roadmap = parse_roadmap(text)

    assert roadmap.milestones == [
        Milestone(id="m1", title="First"),
        Milestone(id="m2", title="Second"),
    ]
    assert len(roadmap.phases) == 2
    assert roadmap.phases[0].milestone_id == "m1"
    assert roadmap.phases[1].milestone_id == "m2"
    assert roadmap.phases[1].outcome == "build beta."
    assert len(roadmap.reqs) == 3
    assert roadmap.reqs_for("P-A") == [Req(id="REQ-A1", text="do alpha", phase_id="P-A")]
    assert {r.id for r in roadmap.reqs_for("P-B")} == {"REQ-B1", "REQ-B2"}


def test_no_reqs():
    text = """\
## Milestone m1 — Empty phase

### Phase P-EMPTY — nothing here

Outcome: no requirements yet.

More prose that is not a REQ line.
"""
    roadmap = parse_roadmap(text)

    assert len(roadmap.milestones) == 1
    assert len(roadmap.phases) == 1
    assert roadmap.phases[0].outcome == "no requirements yet."
    assert roadmap.reqs == []
    assert roadmap.reqs_for("P-EMPTY") == []


def test_load_missing_returns_none(tmp_path: Path):
    assert load_roadmap(tmp_path / ".kalph") is None


def test_prose_and_malformed_lines_ignored():
    text = """\
## Milestone v1 — One

garbage header that should be skipped

### Phase P1 — phase one

Not an outcome line.

- REQ-X1: first req
- not-a-req: ignored
"""
    roadmap = parse_roadmap(text)

    assert len(roadmap.reqs) == 1
    assert roadmap.reqs[0].id == "REQ-X1"
    assert roadmap.phases[0].outcome == ""
