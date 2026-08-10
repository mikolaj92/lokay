from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_CANDIDATES = (
    Path("config.yaml"),
    Path(os.path.expanduser("~/.lokay/config.yaml")),
)


@dataclass
class RepoConfig:
    name: str
    clone_path: Path
    priority: int = 10
    enabled: bool = True
    note: str = ""


@dataclass
class Config:
    mode: str = "dry-run"
    assignee: str = "mikolaj92"
    allow_unassigned: bool = False
    ready_label: str = "ai:ready"
    blocked_label: str = "ai:blocked"
    needs_feedback_label: str = "ai:needs-feedback"
    branch_prefix: str = "ai/fix"
    pr_labels: list[str] = field(default_factory=lambda: ["ai:generated", "ai:pr-opened"])
    repos: list[RepoConfig] = field(default_factory=list)
    executor_enabled: bool = False
    agent: str = "omp"  # log label only
    agent_command: str = "omp"  # harness binary on PATH (executor.command)
    agent_model: str | None = None  # optional; omit from args unless harness needs it
    # Argv after binary. Placeholders: {cwd} {prompt} {model} {max_turns} {timeout}
    # Empty {model} drops a preceding flag + {model} pair.
    agent_args: list[str] = field(
        default_factory=lambda: [
            "--cwd",
            "{cwd}",
            "-p",
            "{prompt}",
            "--auto-approve",
            "--max-time",
            "{timeout}",
        ]
    )
    max_turns: int = 40
    timeout_seconds: int = 1800
    always_approve: bool = True  # kept for harness templates that care; omp uses args
    merge_enabled: bool = False
    require_checks: bool = False
    require_llm_review: bool = True  # structured executor review before auto-merge
    require_test_evidence: bool = True
    worktrees_root: Path = field(default_factory=lambda: Path.home() / ".lokay" / "worktrees")
    state_path: Path = field(default_factory=lambda: Path.home() / ".lokay" / "state.jsonl")
    max_issues_per_tick: int = 1
    max_triage_per_tick: int = 5
    max_repairs_per_tick: int = 1
    max_failures_before_block: int = 2
    min_free_gb: float = 2.0
    config_path: Path | None = None

    @property
    def live(self) -> bool:
        return self.mode == "live"


    def active_repos(self) -> list[RepoConfig]:
        """Enabled repos only (mill / tick iterate these)."""
        return [r for r in self.repos if r.enabled]

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.mode not in {"dry-run", "live"}:
            errors.append(f"mode must be dry-run|live, got {self.mode!r}")
        active = self.active_repos()
        if not active:
            errors.append("repos: at least one enabled repository is required")
        for repo in active:
            if "/" not in repo.name:
                errors.append(f"repo name must be owner/name: {repo.name!r}")
            # Missing clone is not a config error: triage/list still work via gh.
            # Live implement skips or fails per-repo when worktree is needed.
        if self.live and self.executor_enabled and self.max_turns < 1:
            errors.append("executor.max_turns must be >= 1")
        # AI path: empty agent/command is misconfig — fail closed (no invent).
        if not (self.agent or "").strip():
            errors.append("executor.agent must be non-empty (log label for the harness slot)")
        if not (self.agent_command or "").strip():
            errors.append("executor.command must be non-empty")
        if not (self.agent_args or []):
            errors.append("executor.args must be a non-empty argv template")
        # require_checks=false by default: local trust only. Do not gate merges on
        # GitHub Actions / remote CI providers (cost + free-tier limits).
        return errors


def _expand(path: str | Path) -> Path:
    return Path(os.path.expanduser(str(path))).resolve()


def _parse_repo_entries(raw_list: list[Any]) -> list[RepoConfig]:
    repos: list[RepoConfig] = []
    for raw in raw_list or []:
        if not isinstance(raw, dict):
            continue
        repos.append(
            RepoConfig(
                name=str(raw["name"]),
                clone_path=_expand(raw["clone_path"]),
                priority=int(raw.get("priority", 10)),
                enabled=bool(raw.get("enabled", True)),
                note=str(raw.get("note") or ""),
            )
        )
    return repos


def _load_repos(data: dict[str, Any], cfg_path: Path) -> list[RepoConfig]:
    """Load repos from config and optional catalog file (repos_file).

    Catalog entries are base; config `repos:` override/extend by name.
    """
    by_name: dict[str, RepoConfig] = {}

    catalog_ref = data.get("repos_file") or data.get("repos_catalog")
    if catalog_ref:
        cat_path = Path(str(catalog_ref))
        if not cat_path.is_absolute():
            cat_path = (cfg_path.parent / cat_path).resolve()
        else:
            cat_path = _expand(cat_path)
        if cat_path.is_file():
            cat = yaml.safe_load(cat_path.read_text(encoding="utf-8")) or {}
            for repo in _parse_repo_entries(list(cat.get("repos") or [])):
                by_name[repo.name] = repo

    for repo in _parse_repo_entries(list(data.get("repos") or [])):
        by_name[repo.name] = repo  # config wins

    repos = list(by_name.values())
    # Scope = listed repos. Missing clone is a note for operators, not exclusion.
    for repo in repos:
        if not repo.clone_path.exists() and not repo.note:
            repo.note = "clone_path missing — clone before issue_to_pr/worktree"

    repos.sort(key=lambda r: (-r.priority, r.name))
    return repos


def _env_truthy(name: str) -> bool | None:
    """Return True/False if env is set, else None (leave config file value)."""
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return None
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def apply_env_overrides(cfg: Config) -> Config:
    """Apply optional process env overrides for continuous/live mill.

    Safe defaults stay in config.yaml; the factory can enable live milling
    without rewriting the file:

      LOKAY_MODE=live|dry-run
      LOKAY_EXECUTOR_ENABLED=1|0
      LOKAY_AGENT=<label>     (log label; binary is executor.command)
      LOKAY_MERGE_ENABLED=1|0
      LOKAY_REQUIRE_CHECKS=1|0   (0 for no-CI canary repos)
      LOKAY_REQUIRE_LLM_REVIEW=1|0  (structured executor review before merge)
    """
    mode = (os.environ.get("LOKAY_MODE") or "").strip().lower()
    if mode in {"live", "dry-run"}:
        cfg.mode = mode
    v = _env_truthy("LOKAY_EXECUTOR_ENABLED")
    if v is not None:
        cfg.executor_enabled = v
    agent = (os.environ.get("LOKAY_AGENT") or "").strip().lower()
    if agent:
        if agent in {"fake", "stub", "mock", "noop"}:
            raise ValueError(
                f"LOKAY_AGENT={agent!r} forbidden — no stubs"
            )
        cfg.agent = agent
    # Empty agent is misconfig — never re-fill with a silent default.
    if not (cfg.agent or "").strip():
        raise ValueError(
            "executor.agent / LOKAY_AGENT empty — set a non-empty harness label"
        )
    if cfg.agent in {"fake", "stub", "mock", "noop"}:
        raise ValueError(f"agent={cfg.agent!r} forbidden — no stubs")
    if not (cfg.agent_command or "").strip():
        raise ValueError("executor.command empty — set harness binary")
    if not (cfg.agent_args or []):
        raise ValueError("executor.args empty — set argv template")
    v = _env_truthy("LOKAY_MERGE_ENABLED")
    if v is not None:
        cfg.merge_enabled = v
    v = _env_truthy("LOKAY_REQUIRE_CHECKS")
    if v is not None:
        cfg.require_checks = v
    v = _env_truthy("LOKAY_REQUIRE_LLM_REVIEW")
    if v is not None:
        cfg.require_llm_review = v
    return cfg


def load_config(path: str | Path | None = None) -> Config:
    cfg_path: Path | None
    if path is not None:
        cfg_path = _expand(path)
        if not cfg_path.is_file():
            raise FileNotFoundError(f"config not found: {cfg_path}")
    else:
        env = os.environ.get("LOKAY_CONFIG")
        if env:
            cfg_path = _expand(env)
        else:
            cfg_path = next((p.resolve() for p in DEFAULT_CONFIG_CANDIDATES if p.is_file()), None)
        if cfg_path is None:
            raise FileNotFoundError(
                "no config found; run `lokay init` or pass --config"
            )

    data: dict[str, Any] = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    gh = data.get("github") or {}
    ex = data.get("executor") or {}
    mg = data.get("merge") or {}
    wt = data.get("worktrees") or {}
    st = data.get("state") or {}
    lim = data.get("limits") or {}

    repos = _load_repos(data, cfg_path)

    cfg = Config(
        mode=str(data.get("mode", "dry-run")),
        assignee=str(gh.get("assignee", "mikolaj92")),
        allow_unassigned=bool(gh.get("allow_unassigned", False)),
        ready_label=str(gh.get("ready_label", "ai:ready")),
        blocked_label=str(gh.get("blocked_label", "ai:blocked")),
        needs_feedback_label=str(gh.get("needs_feedback_label", "ai:needs-feedback")),
        branch_prefix=str(gh.get("branch_prefix", "ai/fix")),
        pr_labels=list(gh.get("pr_labels") or ["ai:generated", "ai:pr-opened"]),
        repos=repos,
        executor_enabled=bool(ex.get("enabled", False)),
        # Label + binary + argv template. Empty agent/command/args fail closed.
        agent=str(ex.get("agent", "omp")).strip().lower(),
        agent_command=str(ex.get("command", "omp")).strip(),
        agent_model=(str(ex["model"]) if ex.get("model") not in (None, "") else None),
        agent_args=list(ex["args"]) if ex.get("args") is not None else [
            "--cwd",
            "{cwd}",
            "-p",
            "{prompt}",
            "--auto-approve",
            "--max-time",
            "{timeout}",
        ],
        max_turns=int(ex.get("max_turns", 40)),
        timeout_seconds=int(ex.get("timeout_seconds", 1800)),
        always_approve=bool(ex.get("always_approve", True)),
        merge_enabled=bool(mg.get("enabled", False)),
        require_checks=bool(mg.get("require_checks", False)),
        require_llm_review=bool(mg.get("require_llm_review", True)),
        require_test_evidence=bool(mg.get("require_test_evidence", True)),
        worktrees_root=_expand(wt.get("root", "~/.lokay/worktrees")),
        state_path=_expand(st.get("path", "~/.lokay/state.jsonl")),
        max_issues_per_tick=int(lim.get("max_issues_per_tick", 1)),
        max_triage_per_tick=int(lim.get("max_triage_per_tick", 5)),
        max_repairs_per_tick=int(lim.get("max_repairs_per_tick", 1)),
        max_failures_before_block=int(lim.get("max_failures_before_block", 2)),
        min_free_gb=float(lim.get("min_free_gb", 2)),
        config_path=cfg_path,
    )
    return apply_env_overrides(cfg)


def starter_config_text(*, assignee: str = "mikolaj92", repo: str | None = None, clone: str | None = None) -> str:
    example = Path(__file__).resolve().parents[2] / "config.example.yaml"
    text = example.read_text(encoding="utf-8") if example.is_file() else ""
    if not text:
        text = "mode: dry-run\nrepos: []\n"
    if repo and clone:
        block = (
            f"repos:\n"
            f"  - name: {repo}\n"
            f"    clone_path: {clone}\n"
            f"    priority: 10\n"
        )
        if "repos:\n  # - name:" in text:
            text = text.replace(
                "repos:\n  # - name: mikolaj92/lokay\n  #   clone_path: /Users/mikomac/Developer/OSS/lokay\n  #   priority: 10\n",
                block,
            )
        else:
            text += "\n" + block
    text = text.replace("assignee: mikolaj92", f"assignee: {assignee}", 1)
    return text
