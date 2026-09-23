from __future__ import annotations

import os
import re
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
    review_style: str = ""

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
    # Kept for the config file. Never reaches the harness argv.
    agent_model: str | None = None
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
    merge_mode: str = "off"
    require_checks: bool = False
    require_llm_review: bool = True  # structured PR review before auto-merge
    pr_review_engine: str = "open-code-review"
    pr_review_plugin_command: str = ""
    pr_review_plugin_args: list[str] = field(default_factory=list)
    pr_review_plugin_timeout_seconds: int = 7200
    pr_review_provider: str = ""
    pr_review_provider_endpoint_url: str = ""
    pr_review_model: str = ""
    pr_review_config_sha256: str = ""
    pr_review_ocr_config: Path | None = None
    pr_review_manifest: Path | None = None
    pr_review_sandbox_profile: Path | None = None
    pr_review_provider_env: list[str] = field(default_factory=list)
    pr_review_binary: Path | None = None
    pr_review_binary_version: str = "v1.12.7"
    pr_review_binary_sha256: str = ""
    pr_review_effort: str = "medium"
    pr_review_timeout_minutes: int = 30
    pr_review_max_tokens_budget: int = 100000
    pr_review_rule_file: Path | None = None
    pr_review_tools_file: Path | None = None
    pr_review_sandbox_command: list[str] = field(default_factory=list)
    pr_review_artifacts_dir: Path = field(default_factory=lambda: Path.home() / ".lokay" / "pr-review-artifacts")
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


    def __post_init__(self) -> None:
        if self.merge_enabled and self.merge_mode == "off":
            self.merge_mode = "always"

    disabled_repos: list[str] = field(default_factory=list)

    def active_repos(self) -> list[RepoConfig]:
        """Enabled repos only (lokay / tick iterate these)."""
        disabled_env = {
            s.strip()
            for s in os.environ.get("LOKAY_DISABLED_REPOS", "").split(",")
            if s.strip()
        }
        disabled_set = set(self.disabled_repos) | disabled_env
        return [r for r in self.repos if r.enabled and r.name not in disabled_set]

    def review_style_for(self, repo: str) -> str:
        return next(
            (row.review_style for row in self.repos if row.name == repo), ""
        )

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
        if self.max_repairs_per_tick < 0:
            errors.append("limits.max_repairs_per_tick must be >= 0 (fleet pass budget)")
        if self.max_request_changes_per_pr < 1:
            errors.append("limits.max_request_changes_per_pr must be >= 1")
        if self.live and self.merge_enabled and self.require_llm_review:
            if not self.pr_review_plugin_command or not self.pr_review_plugin_args:
                errors.append("pr_review plugin command and args are required for structured review")
            if not self.pr_review_provider_endpoint_url and self.pr_review_provider in {"", "bedrock"}:
                errors.append("pr_review requires an HTTPS provider endpoint URL; implicit provider/credential chains are unsupported")
            if not self.pr_review_provider or not self.pr_review_model:
                errors.append("pr_review provider and model are required for structured review")
            if not re.fullmatch(r"[a-f0-9]{64}", self.pr_review_config_sha256):
                errors.append("trusted pr_review configuration SHA-256 is required")
            if not self.pr_review_binary or not self.pr_review_binary_sha256:
                errors.append("pinned pr_review binary and SHA-256 are required")
            if not self.pr_review_rule_file or not self.pr_review_tools_file:
                errors.append("trusted pr_review rule and tools files are required")
            if not self.pr_review_ocr_config or not self.pr_review_ocr_config.is_file():
                errors.append("trusted OpenCodeReview provider config must exist as a trusted file")
            if not self.pr_review_sandbox_command:
                errors.append("OS sandbox command is required for pr_review")
            if not self.pr_review_sandbox_profile or not self.pr_review_sandbox_profile.is_file():
                errors.append("review OS sandbox profile must exist as a trusted file")
            if not self.pr_review_manifest or not self.pr_review_manifest.is_file():
                errors.append("trusted pr_review config manifest must exist as a trusted file")
            if not self.pr_review_provider_env:
                errors.append("pr_review provider credential environment allowlist is required")
        if self.pr_review_plugin_timeout_seconds < 1:
            errors.append("pr_review.plugin_timeout_seconds must be >= 1")
        if self.pr_review_engine != "open-code-review":
            errors.append("pr_review.engine must be open-code-review in this plugin")
        if self.pr_review_effort not in {"low", "medium", "high"}:
            errors.append("pr_review.effort must be low|medium|high")
        if self.pr_review_timeout_minutes < 1 or self.pr_review_max_tokens_budget < 1:
            errors.append("pr_review runtime limits must be finite and positive")
        if self.pr_review_binary_version != "v1.12.7":
            errors.append("pr_review.binary_version must be pinned to v1.12.7")
        forbidden_env = ("GH_", "GITHUB_", "LOKAY_HEALTH_LEASE")
        for name in self.pr_review_provider_env:
            if not re.fullmatch(r"[A-Z_][A-Z0-9_]*", name) or name.startswith(forbidden_env):
                errors.append(f"pr_review.provider_env contains forbidden name: {name!r}")
        # require_checks=false by default: local trust only. Do not gate merges on
        # GitHub Actions / remote CI providers (cost + free-tier limits).
        return errors


def _expand(path: str | Path) -> Path:
    return Path(os.path.expanduser(str(path))).resolve()


_TRUE_TOKENS = frozenset({"1", "true", "yes", "on"})
_FALSE_TOKENS = frozenset({"0", "false", "no", "off"})


def _yaml_mode(value: Any, *, merge_enabled: bool) -> str:
    """Parse merge.mode. Absent keeps the old meaning of merge.enabled."""
    if value is None or value == "":
        return "always" if merge_enabled else "off"
    mode = str(value).strip().lower()
    if mode not in {"off", "classify", "always"}:
        raise ValueError(f"merge.mode must be off, classify, or always, got {value!r}")
    return mode


def _yaml_bool(value: Any, default: bool, *, field: str) -> bool:
    """Parse a YAML/JSON boolean fail-closed.

    ``bool("false")`` is True in Python — quoted ``enabled: "false"`` must not
    arm the lokay. Accept real bools, 0/1, and the usual truthy/falsy tokens.
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
                review_style=str(raw.get("review_style") or "").strip(),
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
    """Apply optional process env overrides for continuous/live lokay.

    Safe defaults stay in config.yaml; the factory can enable live lokaying
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
    review = data.get("pr_review") or {}

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
        disabled_repos=[str(x).strip() for x in list(data.get("disabled_repos") or []) if str(x).strip()],
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
        merge_mode=_yaml_mode(mg.get("mode"), merge_enabled=_yaml_bool(mg.get("enabled", False), False, field="merge.enabled")),
        require_checks=_yaml_bool(
            mg.get("require_checks", False), False, field="merge.require_checks"
        ),
        require_llm_review=_yaml_bool(
            mg.get("require_llm_review", True), True, field="merge.require_llm_review"
        ),
        pr_review_engine=str(review.get("engine", "open-code-review")),
        pr_review_plugin_command=str(review.get("plugin_command") or ""),
        pr_review_plugin_args=[str(item) for item in review.get("plugin_args") or []],
        pr_review_plugin_timeout_seconds=int(review.get("plugin_timeout_seconds", 7200)),
        pr_review_provider=str(review.get("provider") or ""),
        pr_review_provider_endpoint_url=str(review.get("provider_endpoint_url") or ""),
        pr_review_model=str(review.get("model") or ""),
        pr_review_config_sha256=str(review.get("config_sha256") or "").lower(),
        pr_review_ocr_config=_expand(review["ocr_config"]) if review.get("ocr_config") else None,
        pr_review_manifest=_expand(review["manifest"]) if review.get("manifest") else None,
        pr_review_provider_env=[str(item) for item in review.get("provider_env") or []],
        pr_review_binary=_expand(review["binary"]) if review.get("binary") else None,
        pr_review_binary_version=str(review.get("binary_version", "v1.12.7")),
        pr_review_binary_sha256=str(review.get("binary_sha256") or "").lower(),
        pr_review_effort=str(review.get("effort", "medium")),
        pr_review_timeout_minutes=int(review.get("timeout_minutes", 30)),
        pr_review_max_tokens_budget=int(review.get("max_tokens_budget", 100000)),
        pr_review_rule_file=_expand(review["rule_file"]) if review.get("rule_file") else None,
        pr_review_tools_file=_expand(review["tools_file"]) if review.get("tools_file") else None,
        pr_review_sandbox_command=[str(item) for item in review.get("sandbox_command") or []],
        pr_review_sandbox_profile=_expand(review["sandbox_profile"]) if review.get("sandbox_profile") else None,
        pr_review_artifacts_dir=_expand(review.get("artifacts_dir", "~/.lokay/pr-review-artifacts")),
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
                "repos:\n  # - name: mikolaj92/lokay\n  #   clone_path: ~/Developer/OSS/lokay\n  #   priority: 10\n",
                block,
            )
        else:
            text += "\n" + block
    text = text.replace("assignee: mikolaj92", f"assignee: {assignee}", 1)
    return text
