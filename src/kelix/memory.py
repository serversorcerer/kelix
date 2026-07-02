"""Persistent memory: episodic records, project memory, skills.

Everything is a human-readable file (mission requirement). Layout:

- `.kelix/memory/episodes.jsonl` — runner-owned, gitignored, append-only.
  One record per iteration across all runs: what was attempted, whether it
  verified, how it failed. The digest of recent episodes is injected into
  every iteration prompt (budgeted) so fresh agents don't repeat dead ends.
- `.kelix/memory/project.md` — committed. Durable architecture notes,
  conventions, gotchas. Written by agents during iterations and appended by
  run retrospectives (on the run branch, so updates arrive via PR).
- `.kelix/skills/<name>/SKILL.md` — committed. agentskills.io format.
- `.kelix/fleet/skills/` — runner-side shared store so fleet agents see each
  other's skills before branches merge.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING

from .config import Config

if TYPE_CHECKING:
    from .loop import IterationRecord, RunResult

EPISODES_FILE = "memory/episodes.jsonl"
PROJECT_MEMORY_FILE = "memory/project.md"
SKILLS_DIR = "skills"


# --- episodic memory ---------------------------------------------------------

def record_episode(cfg: Config, rec: IterationRecord, agent_id: str = "solo") -> None:
    if not cfg.memory.enabled:
        return
    path = cfg.kelix_dir / EPISODES_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "agent": agent_id,
        "iteration": rec.index,
        "rationale": rec.rationale,
        "progress": rec.made_progress,
        "verified": rec.verified,
        "failure": rec.failure,
        "duration_s": rec.duration_s,
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def load_episodes(cfg: Config, limit: int = 50) -> list[dict]:
    path = cfg.kelix_dir / EPISODES_FILE
    if not path.is_file():
        return []
    episodes = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            episodes.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # a corrupt line must never kill the loop
    return episodes[-limit:]


def _format_episode_line(ep: dict) -> str:
    outcome = "FAILED: " + ep["failure"] if ep.get("failure") else (
        "verified" if ep.get("verified") else "ok (unverified)"
    )
    rationale = ep.get("rationale") or "(no rationale logged)"
    return f"- [{ep.get('ts', '?')}] {rationale} -> {outcome}"


def _default_budget(lines: list[str]) -> int:
    return sum(len(line) for line in lines) + len(lines)


def episode_digest(
    cfg: Config,
    query: str = "",
    budget_chars: int | None = None,
    manifest: list[dict] | None = None,
) -> str:
    """Compact what-worked/what-failed digest for prompt injection."""
    if not cfg.memory.enabled:
        return ""
    episodes = load_episodes(cfg, limit=cfg.memory.episodes_in_digest)
    if not episodes:
        return ""
    lines = [_format_episode_line(ep) for ep in episodes]
    sources = [
        f".kelix/memory/episodes.jsonl@{ep.get('ts', '?')}" for ep in episodes
    ]
    budget = budget_chars if budget_chars is not None else _default_budget(lines)
    if query.strip():
        from .context import select_scored

        selected = select_scored(lines, query, budget)
        if manifest is not None:
            line_sources = dict(zip(lines, sources, strict=True))
            for text, sc in selected:
                manifest.append(
                    {
                        "slot": "episodes",
                        "source": line_sources.get(text, ".kelix/memory/episodes.jsonl"),
                        "chars": len(text),
                        "score": round(sc, 4),
                    }
                )
        return "\n".join(text for text, _ in selected)
    if manifest is not None:
        for text, src in zip(lines, sources, strict=True):
            manifest.append(
                {
                    "slot": "episodes",
                    "source": src,
                    "chars": len(text),
                    "score": None,
                }
            )
    return "\n".join(lines)


_SECTION_SPLIT = re.compile(r"(?=^## )", re.MULTILINE)


def _project_sections(text: str) -> list[str]:
    parts = [part.strip() for part in _SECTION_SPLIT.split(text) if part.strip()]
    return parts or [text.strip()]


def _section_source(section: str) -> str:
    first = section.split("\n", 1)[0].strip()
    if first.startswith("## "):
        return f".kelix/memory/project.md#{first[3:]}"
    return ".kelix/memory/project.md"


def project_memory_digest(
    cfg: Config,
    workdir: Path | None = None,
    query: str = "",
    budget_chars: int | None = None,
    manifest: list[dict] | None = None,
) -> str:
    """Budgeted project-memory excerpt for prompt injection."""
    if not cfg.memory.enabled:
        return ""
    base = workdir or cfg.root
    path = base / ".kelix" / PROJECT_MEMORY_FILE
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return ""
    sections = _project_sections(text)
    sources = [_section_source(sec) for sec in sections]
    budget = budget_chars if budget_chars is not None else _default_budget(sections)
    if query.strip():
        from .context import select_scored

        selected = select_scored(sections, query, budget)
        if manifest is not None:
            section_sources = dict(zip(sections, sources, strict=True))
            for text_part, sc in selected:
                manifest.append(
                    {
                        "slot": "project_memory",
                        "source": section_sources.get(text_part, ".kelix/memory/project.md"),
                        "chars": len(text_part),
                        "score": round(sc, 4),
                    }
                )
        return "\n\n".join(text for text, _ in selected)
    if len(text) <= budget:
        if manifest is not None:
            manifest.append(
                {
                    "slot": "project_memory",
                    "source": ".kelix/memory/project.md",
                    "chars": len(text),
                    "score": None,
                }
            )
        return text
    excerpt = text[-budget:]
    if manifest is not None:
        manifest.append(
            {
                "slot": "project_memory",
                "source": ".kelix/memory/project.md",
                "chars": len(excerpt),
                "score": None,
            }
        )
    return excerpt


# --- skills -------------------------------------------------------------------

def _parse_skill(path: Path) -> tuple[str, str] | None:
    """Extract (name, description) from SKILL.md YAML frontmatter."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    end = text.find("---", 3)
    if end == -1:
        return None
    name = desc = ""
    for line in text[3:end].splitlines():
        if line.startswith("name:"):
            name = line.split(":", 1)[1].strip()
        elif line.startswith("description:"):
            desc = line.split(":", 1)[1].strip()
    return (name, desc) if name else None


def list_skills(cfg: Config, workdir: Path | None = None) -> list[tuple[str, str, Path]]:
    roots = []
    base = workdir or cfg.root
    roots.append(base / ".kelix" / SKILLS_DIR)
    shared = cfg.kelix_dir / "fleet" / "skills"
    if shared.is_dir():
        roots.append(shared)
    seen: dict[str, tuple[str, str, Path]] = {}
    for root in roots:
        if not root.is_dir():
            continue
        for skill_md in sorted(root.glob("*/SKILL.md")):
            parsed = _parse_skill(skill_md)
            if parsed and parsed[0] not in seen:
                seen[parsed[0]] = (parsed[0], parsed[1], skill_md)
    return list(seen.values())


def skills_digest(
    cfg: Config,
    workdir: Path | None = None,
    query: str = "",
    budget_chars: int | None = None,
    manifest: list[dict] | None = None,
) -> str:
    """Progressive loading, Kiro-style: names + descriptions + path. The agent
    reads the full skill file only when relevant, keeping the prompt cheap."""
    if not cfg.memory.enabled:
        return ""
    skills = list_skills(cfg, workdir)
    if not skills:
        return ""
    lines = [
        f"- {name}: {desc}\n  full steps: {path}" for name, desc, path in skills
    ]
    rel_sources = [
        f".kelix/skills/{path.parent.name}/SKILL.md" for _, _, path in skills
    ]
    budget = budget_chars if budget_chars is not None else _default_budget(lines)
    if query.strip():
        from .context import select_scored

        selected = select_scored(lines, query, budget)
        if manifest is not None:
            line_sources = dict(zip(lines, rel_sources, strict=True))
            for text, sc in selected:
                manifest.append(
                    {
                        "slot": "skills",
                        "source": line_sources.get(text, ".kelix/skills"),
                        "chars": len(text),
                        "score": round(sc, 4),
                    }
                )
        return "\n".join(text for text, _ in selected)
    if manifest is not None:
        for text, src in zip(lines, rel_sources, strict=True):
            manifest.append(
                {
                    "slot": "skills",
                    "source": src,
                    "chars": len(text),
                    "score": None,
                }
            )
    return "\n".join(lines)


# --- retrospectives -----------------------------------------------------------

def write_retrospective(
    cfg: Config,
    result: RunResult,
    run_dir: Path,
    *,
    phase_gate_lines: list[str] | None = None,
) -> None:
    total = len(result.iterations)
    verified = sum(1 for r in result.iterations if r.verified)
    failures = [r for r in result.iterations if r.failure]
    lines = [
        f"# Run {result.run_id} retrospective",
        "",
        f"- status: **{result.status}**",
        f"- iterations: {total} ({verified} verified, {len(failures)} failures)",
        f"- branch: `{result.branch or '(in place)'}`",
        "",
        "## Iterations",
    ]
    for r in result.iterations:
        outcome = f"FAIL ({r.failure})" if r.failure else (
            "verified" if r.verified else "ok"
        )
        lines.append(f"- {r.index}: {r.rationale or '(no rationale)'} -> {outcome}")
    if failures:
        lines += ["", "## For the owner", ""]
        lines += [
            f"- iteration {r.index} needs attention: {r.failure}" for r in failures
        ]
    if phase_gate_lines:
        lines.extend(phase_gate_lines)
    (run_dir / "retrospective.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Update project memory on the run branch so the summary ships in the PR.
    workdir = Path(result.workdir) if result.workdir else cfg.root
    project_md = workdir / ".kelix" / PROJECT_MEMORY_FILE
    if project_md.parent.is_dir():
        with project_md.open("a", encoding="utf-8") as fh:
            fh.write(
                f"\n## Run {result.run_id} ({result.status})\n"
                f"{total} iterations, {verified} verified. "
                + (
                    f"Failures: {'; '.join(r.failure for r in failures)}.\n"
                    if failures
                    else "Clean run.\n"
                )
            )
        from .gitutil import checkpoint, is_repo

        if is_repo(workdir):
            checkpoint(workdir, f"kelix: run {result.run_id} retrospective")
