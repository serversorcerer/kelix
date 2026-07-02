"""``kelix propose`` — self-tuning policy edits on a dedicated branch.

Owner decisions (T-PROPOSE CONTEXT): proposals may touch prompt templates,
security denylist defaults, config defaults, and documented kelix.toml template
keys for ``[memory]`` / ``[loop]`` only. Never backlog, STATE, or roadmap.
"""

from __future__ import annotations

import json
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from .adapters import AdapterError, make_adapter
from .config import Config
from .gitutil import (
    add_worktree,
    checkpoint,
    create_run_branch,
    git,
    head_sha,
    is_repo,
)
from .loop import LoopError, _extract_rationale
from .metrics import load_metrics, metrics_path, metrics_to_dict
from .prompt import PROPOSE_ROLE, assemble_propose_prompt

PREDICTED_IMPROVEMENT_RE = re.compile(r"^PREDICTED_IMPROVEMENT:\s*(.+)$", re.MULTILINE)

# Whole-path allowlist. Partial-file restrictions are documented per entry;
# ST12 validates whole paths only (partial-file guards are documented for review).
PROPOSE_ALLOWED_PREFIXES: tuple[str, ...] = (
    ".kelix/prompts/",
    "src/kelix/security.py",
    "src/kelix/config.py",
    ".kelix/kelix.toml",
    "kelix.toml",
)

# Explicit blocked paths (also checked before prefix allowlist).
PROPOSE_BLOCKED_PATHS: tuple[str, ...] = (
    ".kelix/backlog.md",
    ".kelix/STATE.md",
    ".kelix/roadmap.md",
)

# Partial-file edit surfaces (documentation for ST12 diff validation).
# security.py: only the DEFAULT_DENY constant list (currently lines 52–64).
PROPOSE_SECURITY_EDITABLE = "DEFAULT_DENY denylist patterns only"
# config.py: dataclass field defaults (LoopConfig, MemoryConfig, etc.).
PROPOSE_CONFIG_EDITABLE = "dataclass field defaults in config.py only"
# kelix.toml template: [memory] and [loop] documented keys only (see cli.CONFIG_TEMPLATE).
PROPOSE_KELIX_TOML_EDITABLE = "[memory] and [loop] template keys only"


class ProposeError(Exception):
    pass


def _normalize_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    while normalized.startswith("../"):
        normalized = normalized[3:]
    return normalized


def _is_allowed(path: str) -> bool:
    for prefix in PROPOSE_ALLOWED_PREFIXES:
        if prefix.endswith("/"):
            if path.startswith(prefix) or path == prefix.rstrip("/"):
                return True
        elif path == prefix:
            return True
    return False


def validate_propose_diff(changed_paths: list[str]) -> list[str]:
    """Return violation messages for paths outside the propose allowlist.

    Each changed path is checked against ``PROPOSE_BLOCKED_PATHS`` first, then
    ``PROPOSE_ALLOWED_PREFIXES``. An empty input list returns an empty list.
    """
    violations: list[str] = []
    for raw in changed_paths:
        path = _normalize_path(raw)
        if not path:
            continue
        if path in PROPOSE_BLOCKED_PATHS:
            violations.append(f"{path}: blocked (backlog, STATE, and roadmap are never editable)")
            continue
        if not _is_allowed(path):
            violations.append(f"{path}: not in propose allowlist")
    return violations


def extract_predicted_improvement(output: str) -> str:
    """Return the ``PREDICTED_IMPROVEMENT:`` line from agent output."""
    match = PREDICTED_IMPROVEMENT_RE.search(output)
    return match.group(1).strip() if match else ""


def metrics_excerpt(cfg: Config) -> str:
    """Serialize loop-metrics.json for the proposal prompt."""
    metrics = load_metrics(metrics_path(cfg))
    return json.dumps(metrics_to_dict(metrics), indent=2)


def load_diagnosis_excerpt(cfg: Config, diagnosis_file: str) -> tuple[str, Path | None]:
    """Load optional diagnosis markdown for the proposal prompt."""
    if not diagnosis_file:
        return "", None
    path = Path(diagnosis_file)
    if not path.is_absolute():
        path = cfg.root / path
    if not path.is_file():
        raise ProposeError(f"diagnosis file not found: {path}")
    return path.read_text(encoding="utf-8"), path


def default_proposal_sidecar_path(cfg: Config, *, proposal_id: str | None = None) -> Path:
    """Return ``.kelix/memory/proposal-<id>.json`` under *cfg*."""
    pid = proposal_id or time.strftime("%Y%m%d-%H%M%S")
    return cfg.kelix_dir / "memory" / f"proposal-{pid}.json"


def changed_paths_since(workdir: Path, base_sha: str) -> list[str]:
    """Return paths changed between *base_sha* and HEAD in *workdir*."""
    if not base_sha:
        return []
    names = git(["diff", "--name-only", base_sha, "HEAD"], workdir, check=False).splitlines()
    return [name for name in names if name]


def write_proposal_sidecar(
    path: Path,
    *,
    proposal_id: str,
    run_id: str,
    branch: str,
    prediction: str,
    touched_files: list[str],
    diagnosis_file: str = "",
) -> None:
    """Write the proposal metadata sidecar JSON."""
    payload = {
        "proposal_id": proposal_id,
        "run_id": run_id,
        "branch": branch,
        "prediction": prediction,
        "touched_files": touched_files,
        "diagnosis_file": diagnosis_file,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


@dataclass
class ProposeIteration:
    started_at: str
    duration_s: float = 0.0
    adapter_exit: int = -1
    timed_out: bool = False
    rationale: str = ""
    predicted_improvement: str = ""
    validated: bool = False
    failure: str = ""


@dataclass
class ProposeResult:
    proposal_id: str = ""
    run_id: str = ""
    branch: str = ""
    sidecar_path: Path = Path()
    status: str = "running"  # completed | validation_failed | error
    iteration: ProposeIteration | None = None
    findings: list[str] = field(default_factory=list)
    touched_files: list[str] = field(default_factory=list)


class ProposeRunner:
    """Run ``kelix propose``: one adapter iteration on a dedicated branch."""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg

    def _prepare_workdir(self, run_id: str) -> tuple[Path, str]:
        cfg = self.cfg
        branch = f"{cfg.git.branch_prefix}propose-{run_id}"
        if cfg.git.isolation == "none":
            create_run_branch(cfg.root, branch)
            return cfg.root, branch
        create_run_branch(cfg.root, branch)
        if cfg.git.isolation == "branch":
            git(["checkout", branch], cfg.root)
            return cfg.root, branch
        workdir = cfg.kelix_dir / "worktrees" / run_id
        add_worktree(cfg.root, workdir, branch)
        return workdir, branch

    def _write_transcript(self, run_dir: Path, prompt: str, output: str) -> None:
        from .security import scrub

        if self.cfg.security.scrub_transcripts:
            output = scrub(output)
        (run_dir / "iter-001.log").write_text(
            f"=== PROMPT ===\n{prompt}\n\n=== AGENT OUTPUT ===\n{output}\n",
            encoding="utf-8",
        )

    def _copy_sidecar_to_root(self, workdir: Path, src: Path, dest: Path) -> None:
        if workdir == self.cfg.root:
            return
        if not src.is_file():
            return
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)

    def run(
        self,
        *,
        diagnosis_file: str = "",
        log=print,
    ) -> ProposeResult:
        cfg = self.cfg
        if not is_repo(cfg.root):
            raise LoopError(f"{cfg.root} is not a git repository")

        proposal_id = time.strftime("%Y%m%d-%H%M%S")
        run_id = proposal_id
        result = ProposeResult(
            proposal_id=proposal_id,
            run_id=run_id,
            sidecar_path=default_proposal_sidecar_path(cfg, proposal_id=proposal_id),
        )

        diagnosis_excerpt, diagnosis_path = load_diagnosis_excerpt(cfg, diagnosis_file)
        diagnosis_rel = str(diagnosis_path.relative_to(cfg.root)) if diagnosis_path else ""

        run_dir = cfg.kelix_dir / "runs" / f"propose-{run_id}"
        run_dir.mkdir(parents=True, exist_ok=True)

        workdir, branch = self._prepare_workdir(run_id)
        result.branch = branch

        metrics_text = metrics_excerpt(cfg)
        prompt = assemble_propose_prompt(
            cfg,
            metrics_excerpt=metrics_text,
            diagnosis_excerpt=diagnosis_excerpt,
            role=PROPOSE_ROLE,
        )

        rec = ProposeIteration(started_at=time.strftime("%Y-%m-%dT%H:%M:%S"))
        result.iteration = rec
        started = time.monotonic()
        adapter = make_adapter(cfg)

        log(
            f"kelix propose {run_id}: branch={branch or '(in place)'}; "
            f"sidecar={result.sidecar_path}"
        )
        if diagnosis_rel:
            log(f"  diagnosis: {diagnosis_rel}")

        checkpoint(workdir, f"kelix: pre-propose-{run_id} checkpoint")
        sha_before = head_sha(workdir)

        try:
            agent = adapter.run(prompt, workdir)
        except AdapterError as exc:
            rec.failure = f"adapter error: {exc}"
            rec.duration_s = round(time.monotonic() - started, 1)
            self._write_transcript(run_dir, prompt, rec.failure)
            result.status = "error"
            result.findings = [rec.failure]
            log(f"  propose: {rec.failure}")
            return result

        rec.adapter_exit = agent.exit_code
        rec.timed_out = agent.timed_out
        rec.rationale = _extract_rationale(agent.output)
        rec.predicted_improvement = extract_predicted_improvement(agent.output)
        rec.duration_s = round(time.monotonic() - started, 1)
        self._write_transcript(run_dir, prompt, agent.output)

        checkpoint(workdir, f"kelix: propose-{run_id} checkpoint")
        touched = changed_paths_since(workdir, sha_before)
        violations = validate_propose_diff(touched)

        errors: list[str] = []
        if not agent.ok:
            errors.append(
                f"agent exit {agent.exit_code}" + (" (timeout)" if agent.timed_out else "")
            )
        if not rec.predicted_improvement:
            errors.append("missing PREDICTED_IMPROVEMENT: line in agent output")
        if not touched:
            errors.append("no policy-surface changes committed")
        errors.extend(violations)

        rec.validated = not errors
        result.touched_files = touched

        if errors:
            rec.failure = "; ".join(errors)
            result.status = "validation_failed"
            result.findings = errors
            log(f"  propose: FAIL — {rec.failure}")
            return result

        rel_sidecar = Path(".kelix") / "memory" / f"proposal-{proposal_id}.json"
        workdir_sidecar = workdir / rel_sidecar
        root_sidecar = cfg.root / rel_sidecar
        result.sidecar_path = root_sidecar
        write_proposal_sidecar(
            workdir_sidecar,
            proposal_id=proposal_id,
            run_id=run_id,
            branch=branch,
            prediction=rec.predicted_improvement,
            touched_files=touched,
            diagnosis_file=diagnosis_rel,
        )
        self._copy_sidecar_to_root(workdir, workdir_sidecar, root_sidecar)

        result.status = "completed"
        log(f"  propose: rationale={rec.rationale or '-'} ok")
        log(f"  predicted: {rec.predicted_improvement}")
        return result
