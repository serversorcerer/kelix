from pathlib import Path

from kelix.state import State, load_state, write_state

SAMPLE_STATE = State(
    milestone="v0.2 — Planning Core",
    phase="P-SPINE",
    current_task="PC1",
    last_task="KB7",
    last_verified_commit="abc1234",
    blockers=["REQ-S1 uncovered"],
    done=7,
    total=24,
)


def test_write_load_round_trip(tmp_path: Path):
    kelix = tmp_path / ".kelix"
    kelix.mkdir()
    write_state(kelix, SAMPLE_STATE)
    loaded = load_state(kelix)
    assert loaded == SAMPLE_STATE


def test_load_missing_returns_none(tmp_path: Path):
    assert load_state(tmp_path / ".kelix") is None


def test_partial_file_tolerance(tmp_path: Path):
    kelix = tmp_path / ".kelix"
    kelix.mkdir()
    (kelix / "STATE.md").write_text(
        "# Kelix state\n\n"
        "Some prose the parser should ignore.\n\n"
        "- milestone: v0.2\n"
        "- phase: P-SPINE\n"
        "- done: not-a-number\n"
        "- total: 10\n"
        "- blockers:\n"
        "  - first blocker\n"
        "garbage line\n",
        encoding="utf-8",
    )
    loaded = load_state(kelix)
    assert loaded is not None
    assert loaded.milestone == "v0.2"
    assert loaded.phase == "P-SPINE"
    assert loaded.done == 0
    assert loaded.total == 10
    assert loaded.blockers == ["first blocker"]
    assert loaded.current_task == ""


def test_empty_blockers_round_trip(tmp_path: Path):
    kelix = tmp_path / ".kelix"
    kelix.mkdir()
    state = State(milestone="v0.2", phase="P-SPINE", done=0, total=1)
    write_state(kelix, state)
    loaded = load_state(kelix)
    assert loaded == state
    assert loaded.blockers == []


def test_load_real_repo_state():
    # Structural only: STATE.md's values advance with every run (that is its
    # purpose), so asserting today's phase/counts would rot immediately.
    root = Path(__file__).resolve().parents[1]
    loaded = load_state(root / ".kelix")
    assert loaded is not None
    assert loaded.milestone
    assert loaded.phase
    assert 0 <= loaded.done <= loaded.total
