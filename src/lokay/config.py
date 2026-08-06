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
    agent: str = "grok"  # grok | fake — harness is swappable
    grok_command: str = "grok"
    grok_model: str | None = None
    max_turns: int = 40
    timeout_seconds: int = 1800
    always_approve: bool = True
    merge_enabled: bool = False
    require_checks: bool = True
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

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.mode not in {"dry-run", "live"}:
            errors.append(f"mode must be dry-run|live, got {self.mode!r}")
        if not self.repos:
            errors.append("repos: at least one repository is required")
        for repo in self.repos:
            if "/" not in repo.name:
                errors.append(f"repo name must be owner/name: {repo.name!r}")
            if self.live and not repo.clone_path.exists():
                errors.append(f"clone_path missing for {repo.name}: {repo.clone_path}")
        if self.live and self.executor_enabled and self.max_turns < 1:
            errors.append("executor.max_turns must be >= 1")
        # require_checks=false is allowed: repos without CI can still merge when
        # merge.enabled (explicit opt-in). require_checks=true remains the default.
        return errors


def _expand(path: str | Path) -> Path:
    return Path(os.path.expanduser(str(path))).resolve()


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

    repos: list[RepoConfig] = []
    for raw in data.get("repos") or []:
        repos.append(
            RepoConfig(
                name=str(raw["name"]),
                clone_path=_expand(raw["clone_path"]),
                priority=int(raw.get("priority", 10)),
            )
        )
    repos.sort(key=lambda r: (-r.priority, r.name))

    return Config(
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
        agent=str(ex.get("agent", "grok")).strip().lower() or "grok",
        grok_command=str(ex.get("command", "grok")),
        grok_model=(str(ex["model"]) if ex.get("model") else None),
        max_turns=int(ex.get("max_turns", 40)),
        timeout_seconds=int(ex.get("timeout_seconds", 1800)),
        always_approve=bool(ex.get("always_approve", True)),
        merge_enabled=bool(mg.get("enabled", False)),
        require_checks=bool(mg.get("require_checks", True)),
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
