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

_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off"})
_STUB_AGENTS = frozenset({"fake", "stub", "mock", "noop"})
# Documented example harness for dry-run + executor off only — never invented
# when mode=live or executor.enabled (NO_STUBS / fail closed).
_PI_EXAMPLE_AGENT = "pi"
_PI_EXAMPLE_COMMAND = "pi"


def parse_bool(value: Any, *, default: bool | None = None) -> bool:
    """Parse YAML/env booleans fail-closed.

    ``bool("false")`` is True in Python — never use that for config flags.
    Accepts actual bool, ``0``/``1``, and strings
    ``true``/``false``/``yes``/``no``/``on``/``off`` (any case).
    """
    if value is None:
        if default is None:
            raise ValueError("missing boolean")
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    text = str(value).strip().lower()
    if text in _TRUE:
        return True
    if text in _FALSE:
        return False
    raise ValueError(f"invalid boolean {value!r}")


def _yaml_flag(data: dict[str, Any], key: str, default: bool) -> bool:
    if key not in data:
        return default
    return parse_bool(data[key])


def _mapping(raw: Any, name: str) -> dict[str, Any]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{name} must be a mapping")
    return raw


def _optional_text(data: dict[str, Any], key: str) -> tuple[bool, str]:
    """Return ``(omitted, stripped_text)``. Explicit null/empty is not omitted."""
    if key not in data:
        return True, ""
    raw = data[key]
    if raw is None:
        return False, ""
    return False, str(raw).strip()


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
    agent: str = "pi"  # log label; YAML omitted invents this only in dry-run + executor off
    agent_command: str = "pi"  # harness binary; same: no silent pi when live / enabled
    agent_model: str | None = "omniroute/pi"
    # Argv after binary. Placeholders: {cwd} {prompt} {model} {max_turns} {timeout}
    # Empty {model} drops a preceding flag + {model} pair.
    # Harness flags such as Pi ``--approve`` belong here — there is no always_approve knob.
    agent_args: list[str] = field(
        default_factory=lambda: [
            "-p",
            "{prompt}",
            "--model",
            "{model}",
            "--approve",
            "--no-session",
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
        repos.append(
            RepoConfig(
                name=str(raw["name"]),
                clone_path=_expand(raw["clone_path"]),
                priority=int(raw.get("priority", 10)),
                enabled=_yaml_flag(raw, "enabled", True),
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


def _env_bool(name: str) -> bool | None:
    """Return True/False if env is set, else None (leave config file value)."""
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return None
    try:
        return parse_bool(raw)
    except ValueError as exc:
        raise ValueError(f"{name}={raw!r} is not a boolean") from exc


def apply_env_overrides(
    cfg: Config,
    *,
    agent_omitted: bool = False,
    command_omitted: bool = False,
) -> Config:
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
    v = _env_bool("LOKAY_EXECUTOR_ENABLED")
    if v is not None:
        cfg.executor_enabled = v
    agent_env = (os.environ.get("LOKAY_AGENT") or "").strip().lower()
    if agent_env:
        if agent_env in _STUB_AGENTS:
            raise ValueError(
                f"LOKAY_AGENT={agent_env!r} forbidden — no stubs"
            )
        cfg.agent = agent_env
        agent_omitted = False
    _resolve_harness(
        cfg, agent_omitted=agent_omitted, command_omitted=command_omitted
    )
    v = _env_bool("LOKAY_MERGE_ENABLED")
    if v is not None:
        cfg.merge_enabled = v
    v = _env_bool("LOKAY_REQUIRE_CHECKS")
    if v is not None:
        cfg.require_checks = v
    v = _env_bool("LOKAY_REQUIRE_LLM_REVIEW")
    if v is not None:
        cfg.require_llm_review = v
    return cfg


def _resolve_harness(
    cfg: Config, *, agent_omitted: bool, command_omitted: bool
) -> None:
    """Fail closed on empty/omitted harness when live milling or executor is on.

    Dry-run with executor off may keep the documented Pi example. Explicit
    empty agent/command always fails (you set nothing).
    """
    live_or_exec = cfg.live or cfg.executor_enabled
    command = (cfg.agent_command or "").strip()
    if not command:
        if not command_omitted:
            raise ValueError("executor.command empty — set harness binary")
        if live_or_exec:
            raise ValueError(
                "executor.command omitted — set harness binary "
                "(no silent pi default when mode=live or executor.enabled)"
            )
        command = _PI_EXAMPLE_COMMAND
    cfg.agent_command = command

    agent = (cfg.agent or "").strip().lower()
    if not agent:
        if not agent_omitted:
            raise ValueError(
                "executor.agent / LOKAY_AGENT empty — set a non-empty harness label"
            )
        if live_or_exec:
            # Do not invent "pi"; the log label follows the configured binary.
            agent = Path(command).name.strip().lower()
            if not agent:
                raise ValueError(
                    "executor.agent omitted — set a non-empty harness label "
                    "(no silent pi default when mode=live or executor.enabled)"
                )
        else:
            agent = _PI_EXAMPLE_AGENT
    if agent in _STUB_AGENTS:
        raise ValueError(f"agent={agent!r} forbidden — no stubs")
    cfg.agent = agent
    if not (cfg.agent_args or []):
        raise ValueError("executor.args empty — set argv template")


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
    gh = _mapping(data.get("github"), "github")
    ex = _mapping(data.get("executor"), "executor")
    mg = _mapping(data.get("merge"), "merge")
    wt = _mapping(data.get("worktrees"), "worktrees")
    st = _mapping(data.get("state"), "state")
    lim = _mapping(data.get("limits"), "limits")

    repos = _load_repos(data, cfg_path)
    agent_omitted, agent_text = _optional_text(ex, "agent")
    command_omitted, command_text = _optional_text(ex, "command")

    cfg = Config(
        mode=str(data.get("mode", "dry-run")),
        assignee=str(gh.get("assignee", "mikolaj92")),
        allow_unassigned=_yaml_flag(gh, "allow_unassigned", False),
        ready_label=str(gh.get("ready_label", "ai:ready")),
        blocked_label=str(gh.get("blocked_label", "ai:blocked")),
        needs_feedback_label=str(gh.get("needs_feedback_label", "ai:needs-feedback")),
        branch_prefix=str(gh.get("branch_prefix", "ai/fix")),
        pr_labels=list(gh.get("pr_labels") or ["ai:generated", "ai:pr-opened"]),
        repos=repos,
        executor_enabled=_yaml_flag(ex, "enabled", False),
        # Label + binary. Omitted command/agent invent Pi only in dry-run +
        # executor off; live / enabled fail closed (NO_STUBS).
        agent=agent_text.lower(),
        agent_command=command_text,
        agent_model=(
            str(ex["model"]) if ex.get("model") not in (None, "") else "omniroute/pi"
        ),
        agent_args=list(ex["args"]) if ex.get("args") is not None else [
            "-p",
            "{prompt}",
            "--model",
            "{model}",
            "--approve",
            "--no-session",
        ],
        max_turns=int(ex.get("max_turns", 40)),
        timeout_seconds=int(ex.get("timeout_seconds", 1800)),
        merge_enabled=_yaml_flag(mg, "enabled", False),
        require_checks=_yaml_flag(mg, "require_checks", False),
        require_llm_review=_yaml_flag(mg, "require_llm_review", True),
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
        config_path=cfg_path,
    )
    return apply_env_overrides(
        cfg, agent_omitted=agent_omitted, command_omitted=command_omitted
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
