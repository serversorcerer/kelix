"""Post-retrospective skill distillation pass.

After ``write_retrospective``, the runner may invoke the configured adapter once
with a fixed distillation prompt over the run's transcripts and episode outcomes.
Candidates land under ``.kelix/skills/_proposed/<name>/SKILL.md`` only.
"""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from .adapters import AdapterError, make_adapter
from .config import Config
from .gitutil import checkpoint, head_sha, is_repo
from .loop import RunResult
from .memory import PROPOSED_SKILLS_DIR, SKILLS_DIR, _parse_skill
from .prompt import DISTILLATION_ROLE, assemble_distillation_prompt
from .propose import changed_paths_since

MAX_DISTILL_CANDIDATES = 3
PROPOSED_SKILL_PREFIX = f".kelix/{SKILLS_DIR}/{PROPOSED_SKILLS_DIR}/"


def _normalize_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    while normalized.startswith("../"):
        normalized = normalized[3:]
    return normalized


def validate_distillation_diff(changed_paths: list[str]) -> list[str]:
    """Return violation messages for paths outside the distillation allowlist."""
    violations: list[str] = []
    for raw in changed_paths:
        path = _normalize_path(raw)
        if not path:
            continue
        if not path.startswith(PROPOSED_SKILL_PREFIX):
            violations.append(f"{path}: not under {PROPOSED_SKILL_PREFIX}")
            continue
        rel = path[len(PROPOSED_SKILL_PREFIX) :]
        parts = rel.split("/")
        if len(parts) != 2 or parts[1] != "SKILL.md":
            violations.append(f"{path}: must be _proposed/<name>/SKILL.md only")
    return violations


def load_run_transcripts(run_dir: Path) -> str:
    """Concatenate iteration transcripts from a run directory."""
    parts: list[str] = []
    for path in sorted(run_dir.glob("iter-*.log")):
        parts.append(f"## {path.name}\n\n{path.read_text(encoding='utf-8')}")
    return "\n\n".join(parts)


def format_episode_outcomes(result: RunResult) -> str:
    """Summarize iteration outcomes for the distillation prompt."""
    lines: list[str] = []
    for rec in result.iterations:
        if rec.failure:
            outcome = f"FAIL ({rec.failure})"
        elif rec.verified:
            outcome = "verified"
        else:
            outcome = "ok"
        rationale = rec.rationale or "(none)"
        lines.append(
            f"- iteration {rec.index}: {rationale} -> {outcome} "
            f"(duration {rec.duration_s}s)"
        )
    return "\n".join(lines) if lines else "(no iterations)"


def _proposed_skills_root(workdir: Path) -> Path:
    return workdir / ".kelix" / SKILLS_DIR / PROPOSED_SKILLS_DIR


def list_proposed_skill_dirs(workdir: Path) -> list[Path]:
    """Return skill candidate directories containing SKILL.md."""
    base = _proposed_skills_root(workdir)
    if not base.is_dir():
        return []
    return sorted(
        entry for entry in base.iterdir() if entry.is_dir() and (entry / "SKILL.md").is_file()
    )


def enforce_skill_cap(workdir: Path, log) -> list[str]:
    """Validate frontmatter and cap candidates; drop extras beyond the limit."""
    dirs = list_proposed_skill_dirs(workdir)
    valid: list[tuple[str, Path]] = []
    for entry in dirs:
        skill_md = entry / "SKILL.md"
        parsed = _parse_skill(skill_md)
        if parsed:
            valid.append((entry.name, skill_md))
        else:
            log(f"  distill: invalid frontmatter in {skill_md.relative_to(workdir)}, ignoring")

    if len(valid) > MAX_DISTILL_CANDIDATES:
        log(
            f"  distill: warning — {len(valid)} candidates exceed cap "
            f"{MAX_DISTILL_CANDIDATES}; dropping extras"
        )
        proposed_root = _proposed_skills_root(workdir)
        for name, _ in valid[MAX_DISTILL_CANDIDATES:]:
            shutil.rmtree(proposed_root / name, ignore_errors=True)
        valid = valid[:MAX_DISTILL_CANDIDATES]

    return [name for name, _ in valid]


@dataclass
class DistillResult:
    skill_names: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _write_distill_transcript(run_dir: Path, prompt: str, output: str, cfg: Config) -> None:
    from .security import scrub

    if cfg.security.scrub_transcripts:
        output = scrub(output)
    distill_dir = run_dir / "distill"
    distill_dir.mkdir(parents=True, exist_ok=True)
    (distill_dir / "distill.log").write_text(
        f"=== PROMPT ===\n{prompt}\n\n=== AGENT OUTPUT ===\n{output}\n",
        encoding="utf-8",
    )


def run_distillation(
    cfg: Config,
    result: RunResult,
    run_dir: Path,
    *,
    transcripts: str = "",
    episode_outcomes: str = "",
    workdir: Path | None = None,
    log=print,
) -> DistillResult:
    """Run one distillation adapter pass after retrospective."""
    if not cfg.memory.enabled or not cfg.memory.distill_skills:
        return DistillResult()

    target = workdir or (Path(result.workdir) if result.workdir else cfg.root)
    tx = transcripts if transcripts else load_run_transcripts(run_dir)
    episodes = episode_outcomes if episode_outcomes else format_episode_outcomes(result)

    prompt = assemble_distillation_prompt(
        cfg,
        transcripts=tx,
        episode_outcomes=episodes,
        role=DISTILLATION_ROLE,
    )

    adapter = make_adapter(cfg)
    sha_before = head_sha(target) if is_repo(target) else ""

    started = time.monotonic()
    try:
        agent = adapter.run(prompt, target)
    except AdapterError as exc:
        log(f"  distill: adapter error: {exc}")
        return DistillResult(warnings=[str(exc)])

    duration = round(time.monotonic() - started, 1)
    self_output = agent.output
    _write_distill_transcript(run_dir, prompt, self_output, cfg)

    if not agent.ok:
        msg = f"agent exit {agent.exit_code}" + (" (timeout)" if agent.timed_out else "")
        log(f"  distill: {msg} ({duration}s)")
        return DistillResult(warnings=[msg])

    touched = changed_paths_since(target, sha_before)
    violations = validate_distillation_diff(touched)
    if violations:
        for violation in violations:
            log(f"  distill: {violation}")
        return DistillResult(warnings=violations)

    names = enforce_skill_cap(target, log)
    if names and is_repo(target):
        checkpoint(target, f"kelix: distill {result.run_id} ({len(names)} skill(s))")
        log(f"  distill: {len(names)} candidate(s): {', '.join(names)} ({duration}s)")
    elif not names:
        log(f"  distill: no valid candidates written ({duration}s)")

    return DistillResult(skill_names=names)


def run_fleet_distillation(
    cfg: Config,
    results: dict[str, RunResult],
    *,
    log=print,
) -> DistillResult:
    """One distillation pass aggregating transcripts from a fleet run."""
    if not cfg.memory.enabled or not cfg.memory.distill_skills or not results:
        return DistillResult()

    transcript_parts: list[str] = []
    episode_parts: list[str] = []
    primary: RunResult | None = None

    for agent_id, result in sorted(results.items()):
        run_dir = cfg.kelix_dir / "runs" / result.run_id
        tx = load_run_transcripts(run_dir)
        if tx:
            transcript_parts.append(f"# Agent {agent_id}\n\n{tx}")
        ep = format_episode_outcomes(result)
        episode_parts.append(f"## Agent {agent_id}\n{ep}")
        if primary is None:
            primary = result

    if primary is None:
        return DistillResult()

    combined_tx = "\n\n".join(transcript_parts) or "(no transcripts available)"
    combined_ep = "\n\n".join(episode_parts)
    fleet_run_dir = cfg.kelix_dir / "runs" / f"fleet-distill-{primary.run_id}"

    return run_distillation(
        cfg,
        primary,
        fleet_run_dir,
        transcripts=combined_tx,
        episode_outcomes=combined_ep,
        workdir=cfg.root,
        log=log,
    )
