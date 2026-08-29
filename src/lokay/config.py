from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from lokay.catalog import (
    CatalogBinding,
    CatalogError,
    DEFAULT_PLUGIN,
    assert_known_plugins,
    parse_catalog_row,
)

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
    issues: CatalogBinding | None = None
    code: CatalogBinding | None = None

    def __post_init__(self) -> None:
        # Parent still keys GitHub by name. Missing sides default to github + name.
        if self.issues is None:
            self.issues = CatalogBinding(DEFAULT_PLUGIN, self.name)
        if self.code is None:
            self.code = CatalogBinding(DEFAULT_PLUGIN, self.name)


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
    agent: str = "pi"  # log label only
    agent_command: str = "pi"  # harness binary on PATH (executor.command)
    agent_model: str | None = "omniroute/pi"
    # Argv after binary. Placeholders: {cwd} {prompt} {model} {max_turns} {timeout} {session}
    # Empty {model} drops a preceding flag + {model} pair.
    agent_args: list[str] = field(
        default_factory=lambda: [
            "-p",
            "{prompt}",
            "--model",
            "{model}",
            "--approve",
            "--session-id",
            "{session}",
        ]
    )
    max_turns: int = 40
    timeout_seconds: int = 1800
    merge_enabled: bool = False
    require_checks: bool = False
    require_llm_review: bool = True  # structured executor review before auto-merge
    worktrees_root: Path = field(default_factory=lambda: Path.home() / ".lokay" / "worktrees")
    state_path: Path = field(default_factory=lambda: Path.home() / ".lokay" / "state.jsonl")
    # K: optional pass budget for issue_to_pr (serial by design; default 1).
    # Not concurrent worktrees / Pi / tmux — ticket after ticket.
    max_issue_to_pr_per_pass: int = 1
    # Legacy alias kept in sync with max_issue_to_pr_per_pass on load.
    max_issues_per_tick: int = 1
    max_triage_per_tick: int = 5
    max_repairs_per_tick: int = 1
    max_request_changes_per_pr: int = 2  # then escalate to ai:needs-review
    max_failures_before_block: int = 2
    min_free_gb: float = 2.0
    # Incident filing target + spam control (preflight / recovery).
    incident_repo: str = "mikolaj92/lokay"
    incident_cooldown_hours: float = 12.0
    # Survey / gh budget: bounded 429 retries and optional inter-call pacing.
    gh_retry_max: int = 3
    gh_survey_pace_ms: int = 50
    # Parent department switches (one Fala graph = one department). Independent
    # of executor.enabled (harness). Disabling executor must not disable sieves.
    department_self_repair: bool = True
    department_issue_triage: bool = True
    department_executor: bool = True
    department_pr_triage: bool = True
    department_pr_repair: bool = True
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
        # Identity is required only when the harness can run — no silent Pi invent.
        if self.executor_enabled:
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


_TRUE_TOKENS = frozenset({"1", "true", "yes", "on"})
_FALSE_TOKENS = frozenset({"0", "false", "no", "off"})


def _yaml_bool(value: Any, default: bool, *, field: str) -> bool:
    """Parse a YAML/JSON boolean fail-closed.

    ``bool("false")`` is True in Python — quoted ``enabled: "false"`` must not
    arm the mill. Accept real bools, 0/1, and the usual truthy/falsy tokens.
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        token = value.strip().lower()
        if token in _TRUE_TOKENS:
            return True
        if token in _FALSE_TOKENS:
            return False
    raise ValueError(f"{field} must be a boolean, got {value!r}")


def _limit_issue_to_pr_per_pass(lim: dict[str, Any]) -> int:
    """Resolve K pass budget for issue_to_pr (default 1; serial by design).

    Prefer ``max_issue_to_pr_per_pass``; fall back to legacy ``max_issues_per_tick``.
    K>1 is a rare breadth knob across already-isolated clean repos — not
    concurrent worktrees/Pi/tmux.
    """
    if "max_issue_to_pr_per_pass" in lim:
        return int(lim["max_issue_to_pr_per_pass"])
    if "max_issues_per_tick" in lim:
        return int(lim["max_issues_per_tick"])
    return 1


def _parse_repo_entries(raw_list: list[Any]) -> list[RepoConfig]:
    repos: list[RepoConfig] = []
    for raw in raw_list or []:
        if not isinstance(raw, dict):
            continue
        row = parse_catalog_row(raw)
        assert_known_plugins(row)
        if not row.clone_path:
            raise CatalogError(f"catalog row {row.name!r} needs clone_path")
        repos.append(
            RepoConfig(
                name=row.name,
                clone_path=_expand(row.clone_path),
                priority=int(raw.get("priority", 10)),
                enabled=_yaml_bool(
                    raw.get("enabled", True), True, field=f"repos[{row.name}].enabled"
                ),
                note=str(raw.get("note") or ""),
                issues=row.issues,
                code=row.code,
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
    # Empty identity is misconfig only when the harness can run — no silent Pi.
    if cfg.executor_enabled:
        if not (cfg.agent or "").strip() and (cfg.agent_command or "").strip():
            cfg.agent = str(cfg.agent_command).strip().lower()
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
    elif (cfg.agent or "").strip() in {"fake", "stub", "mock", "noop"}:
        raise ValueError(f"agent={cfg.agent!r} forbidden — no stubs")
    v = _env_truthy("LOKAY_MERGE_ENABLED")
    if v is not None:
        cfg.merge_enabled = v
    v = _env_truthy("LOKAY_REQUIRE_CHECKS")
    if v is not None:
        cfg.require_checks = v
    v = _env_truthy("LOKAY_REQUIRE_LLM_REVIEW")
    if v is not None:
        cfg.require_llm_review = v
    for env_name, attr in (
        ("LOKAY_DEPARTMENT_SELF_REPAIR", "department_self_repair"),
        ("LOKAY_DEPARTMENT_ISSUE_TRIAGE", "department_issue_triage"),
        ("LOKAY_DEPARTMENT_EXECUTOR", "department_executor"),
        ("LOKAY_DEPARTMENT_PR_TRIAGE", "department_pr_triage"),
        ("LOKAY_DEPARTMENT_PR_REPAIR", "department_pr_repair"),
    ):
        flag = _env_truthy(env_name)
        if flag is not None:
            setattr(cfg, attr, flag)
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

    raw_args = ex.get("args")
    if raw_args is None:
        agent_args: list[str] = []
    elif not isinstance(raw_args, list):
        raise ValueError("executor.args must be a YAML list")
    else:
        agent_args = [str(item) for item in raw_args]

    cfg = Config(
        mode=str(data.get("mode", "dry-run")),
        assignee=str(gh.get("assignee", "mikolaj92")),
        allow_unassigned=_yaml_bool(
            gh.get("allow_unassigned", False), False, field="github.allow_unassigned"
        ),
        ready_label=str(gh.get("ready_label", "ai:ready")),
        blocked_label=str(gh.get("blocked_label", "ai:blocked")),
        needs_feedback_label=str(gh.get("needs_feedback_label", "ai:needs-feedback")),
        branch_prefix=str(gh.get("branch_prefix", "ai/fix")),
        pr_labels=list(gh.get("pr_labels") or ["ai:generated", "ai:pr-opened"]),
        repos=repos,
        executor_enabled=_yaml_bool(
            ex.get("enabled", False), False, field="executor.enabled"
        ),
        # Omit identity → empty (fail closed when enabled). Never invent Pi.
        agent=str(ex["agent"]).strip().lower() if ex.get("agent") not in (None, "") else "",
        agent_command=str(ex["command"]).strip() if ex.get("command") not in (None, "") else "",
        agent_model=(
            str(ex["model"]).strip() if ex.get("model") not in (None, "") else None
        ),
        agent_args=agent_args,
        max_turns=int(ex.get("max_turns", 40)),
        timeout_seconds=int(ex.get("timeout_seconds", 1800)),
        merge_enabled=_yaml_bool(mg.get("enabled", False), False, field="merge.enabled"),
        require_checks=_yaml_bool(
            mg.get("require_checks", False), False, field="merge.require_checks"
        ),
        require_llm_review=_yaml_bool(
            mg.get("require_llm_review", True), True, field="merge.require_llm_review"
        ),
        worktrees_root=_expand(wt.get("root", "~/.lokay/worktrees")),
        state_path=_expand(st.get("path", "~/.lokay/state.jsonl")),
        max_issue_to_pr_per_pass=(
            _limit_issue_to_pr_per_pass(lim)
        ),
        max_issues_per_tick=(
            _limit_issue_to_pr_per_pass(lim)
        ),
        max_triage_per_tick=int(lim.get("max_triage_per_tick", 5)),
        max_repairs_per_tick=int(lim.get("max_repairs_per_tick", 1)),
        max_request_changes_per_pr=int(lim.get("max_request_changes_per_pr", 2)),
        max_failures_before_block=int(lim.get("max_failures_before_block", 2)),
        min_free_gb=float(lim.get("min_free_gb", 2)),
        incident_repo=str(gh.get("incident_repo") or "mikolaj92/lokay").strip()
        or "mikolaj92/lokay",
        incident_cooldown_hours=float(gh.get("incident_cooldown_hours", 12)),
        gh_retry_max=int(lim.get("gh_retry_max", 3)),
        gh_survey_pace_ms=int(lim.get("gh_survey_pace_ms", 50)),
        department_self_repair=_yaml_bool(
            (data.get("departments") or {}).get("self_repair", True),
            True,
            field="departments.self_repair",
        ),
        department_issue_triage=_yaml_bool(
            (data.get("departments") or {}).get("issue_triage", True),
            True,
            field="departments.issue_triage",
        ),
        department_executor=_yaml_bool(
            (data.get("departments") or {}).get("executor", True),
            True,
            field="departments.executor",
        ),
        department_pr_triage=_yaml_bool(
            (data.get("departments") or {}).get("pr_triage", True),
            True,
            field="departments.pr_triage",
        ),
        department_pr_repair=_yaml_bool(
            (data.get("departments") or {}).get("pr_repair", True),
            True,
            field="departments.pr_repair",
        ),
        config_path=cfg_path,
    )
    return apply_env_overrides(cfg)


DEPARTMENT_ATTR = {
    "self_repair": "department_self_repair",
    "issue_triage": "department_issue_triage",
    "executor": "department_executor",
    "pr_triage": "department_pr_triage",
    "pr_repair": "department_pr_repair",
}


def department_enabled(cfg: Config, name: str) -> bool:
    """On/off switch for one named parent department."""
    return bool(getattr(cfg, DEPARTMENT_ATTR[name]))


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
