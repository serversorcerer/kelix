"""Kelix configuration.

Config lives in `.kelix/kelix.toml` (preferred) or `kelix.toml` at the repo
root. Every field has a default chosen to be safe to run unattended; a repo
with no config file at all gets a working, conservative setup.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_LOCATIONS = (".kelix/kelix.toml", "kelix.toml")


@dataclass
class AgentConfig:
    adapter: str = "kiro"  # kiro | cmd | mock
    # For the `cmd` adapter: template tokens {prompt_file} and {prompt} are
    # substituted. For `kiro` this is ignored (built-in command line).
    command: str = ""
    # Extra args appended to the kiro adapter invocation (e.g. ["--agent", "kelix"]).
    kiro_args: list[str] = field(default_factory=list)
    timeout_seconds: int = 1800
    # Kill the agent if stdout/stderr is silent this long (seconds). 0 disables.
    inactivity_timeout_seconds: int = 300
    # For the `mock` adapter: directory of numbered scripts (see adapters.py).
    mock_dir: str = ""


@dataclass
class LoopConfig:
    max_iterations: int = 25
    # Stop after this many consecutive iterations that error or produce no diff.
    circuit_breaker_threshold: int = 3
    plan_file: str = ".kelix/backlog.md"
    prompt_file: str = ".kelix/prompts/iteration.md"
    # kelix diagnose: max chars of failed transcripts to inject; default run count.
    diagnose_transcript_chars: int = 50000
    diagnose_default_runs: int = 3


@dataclass
class VerifyConfig:
    # Commands that must all exit 0 for a task to be verified-done.
    commands: list[str] = field(default_factory=list)
    timeout_seconds: int = 600


@dataclass
class MemoryConfig:
    enabled: bool = True
    context_share: float = 0.5
    state_max_chars: int = 1200
    phase_context_max_chars: int = 2000
    digest_max_chars: int = 8000
    project_max_chars: int = 4000
    skills_max_chars: int = 6000
    mailbox_max_chars: int = 2000
    episodes_in_digest: int = 10


@dataclass
class AutonomyConfig:
    # "normal": self-proposed tasks always rank below owner tasks.
    # "high": proposed tasks compete on score alone.
    level: str = "normal"


@dataclass
class SecurityConfig:
    # Extra denied command patterns on top of built-in defaults (security.py).
    deny_extra: list[str] = field(default_factory=list)
    # If set, ONLY these command prefixes are allowed (allowlist mode).
    allow_only: list[str] = field(default_factory=list)
    scrub_transcripts: bool = True


@dataclass
class GitConfig:
    branch_prefix: str = "kelix/"
    # worktree: run in an isolated git worktree (default, safest)
    # branch:   run in-place on a fresh branch
    # none:     run in-place on the current branch (tests/CI only)
    isolation: str = "worktree"


@dataclass
class TrackerConfig:
    # Issue-tracker sync. Disabled unless explicitly configured.
    provider: str = ""  # "" | "linear"
    team: str = ""


@dataclass
class Config:
    root: Path = field(default_factory=Path.cwd)
    agent: AgentConfig = field(default_factory=AgentConfig)
    loop: LoopConfig = field(default_factory=LoopConfig)
    verify: VerifyConfig = field(default_factory=VerifyConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    autonomy: AutonomyConfig = field(default_factory=AutonomyConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    git: GitConfig = field(default_factory=GitConfig)
    tracker: TrackerConfig = field(default_factory=TrackerConfig)

    @property
    def kelix_dir(self) -> Path:
        return self.root / ".kelix"


_SECTIONS = {
    "agent": AgentConfig,
    "loop": LoopConfig,
    "verify": VerifyConfig,
    "memory": MemoryConfig,
    "autonomy": AutonomyConfig,
    "security": SecurityConfig,
    "git": GitConfig,
    "tracker": TrackerConfig,
}


class ConfigError(Exception):
    pass


def _build_section(cls, data: dict, section: str):
    kwargs = {}
    valid = {f for f in cls.__dataclass_fields__}
    for key, value in data.items():
        if key not in valid:
            raise ConfigError(f"unknown key [{section}].{key}")
        expected = type(getattr(cls(), key))
        if not isinstance(value, expected):
            raise ConfigError(
                f"[{section}].{key} must be {expected.__name__}, got {type(value).__name__}"
            )
        kwargs[key] = value
    return cls(**kwargs)


def load_config(root: Path | None = None) -> Config:
    root = (root or Path.cwd()).resolve()
    raw: dict = {}
    for rel in CONFIG_LOCATIONS:
        path = root / rel
        if path.is_file():
            raw = tomllib.loads(path.read_text(encoding="utf-8"))
            break

    cfg = Config(root=root)
    for section, cls in _SECTIONS.items():
        if section in raw:
            if not isinstance(raw[section], dict):
                raise ConfigError(f"[{section}] must be a table")
            setattr(cfg, section, _build_section(cls, raw[section], section))

    if cfg.agent.adapter not in ("kiro", "cmd", "mock"):
        raise ConfigError(f"unknown agent adapter {cfg.agent.adapter!r}")
    if cfg.agent.adapter == "cmd" and not cfg.agent.command:
        raise ConfigError("[agent].command is required when adapter = 'cmd'")
    if cfg.git.isolation not in ("worktree", "branch", "none"):
        raise ConfigError(f"unknown git isolation {cfg.git.isolation!r}")
    if cfg.autonomy.level not in ("normal", "high"):
        raise ConfigError(f"unknown autonomy level {cfg.autonomy.level!r}")
    share = cfg.memory.context_share
    if not isinstance(share, float) or not (0.0 <= share <= 1.0):
        raise ConfigError("[memory].context_share must be a float between 0 and 1")
    return cfg
