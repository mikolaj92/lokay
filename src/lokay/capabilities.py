"""Stable role capabilities independent of the selected harness."""
from __future__ import annotations

import os
from importlib.resources import files
from typing import Mapping

ROLE_CAPABILITIES = {
    "builder": {"code.write"},
    "reviewer": {"evidence.read", "verdict.propose"},
    "department": {
        "github.read",
        "github.write",
        "git.write",
        "code.write",
        "pr.create",
        "pr.merge",
        "issue.close",
        "verdict.propose",
    },
    "acceptance_effect": {"acceptance.write"},
    "push_effect": {"git.push"},
    "merge_effect": {"pr.merge"},
    "close_effect": {"issue.close"},
    "pr_effect": {"pr.create"},
}

_AGENT_ROLES = frozenset({"builder", "reviewer"})
_DEPARTMENT_ENV_KEYS = frozenset({
    "PATH",
    "HOME",
    "USER",
    "SHELL",
    "TMPDIR",
    "LANG",
    "TERM",
    "GH_TOKEN",
    "GH_HOST",
    "GH_CONFIG_DIR",
    "GH_ENTERPRISE_TOKEN",
    "GITHUB_TOKEN",
    "XDG_CONFIG_HOME",
    "SSH_AUTH_SOCK",
    "LOKAY_CONFIG",
    "LOKAY_ROOT",
    "LOKAY_AGENT",
})
_DEPARTMENT_ENV_PREFIXES = (
    "GH_",
    "GITHUB_",
    "OMNIROUTE_",
    "PI_",
    "OPENAI_",
    "ANTHROPIC_",
    "XAI_",
)


def _deny_bin_dir() -> str:
    return str(files("lokay").joinpath("data", "deny-bin"))


def coding_path(ambient_path: str) -> str:
    """Prepend deny-bin so `gh` resolves to a fail-closed stub in coding slots."""
    deny = _deny_bin_dir()
    path = (ambient_path or "").strip()
    if not path:
        return deny
    return f"{deny}{os.pathsep}{path}"


def executor_environment(role: str, ambient: Mapping[str, str]) -> dict[str, str]:
    """Build the process env for an executor role.

    Builder/reviewer env is allowlist-only: ``PATH`` (deny-bin first) and
    ``LOKAY_CAPABILITIES``. Ambient secrets (``GH_*``, ``GITHUB_*``, leases,
    etc.) are never copied into agent roles — isolation is deny-bin + this
    allowlist, not a post-hoc credential scrub.
    """
    caps = ROLE_CAPABILITIES.get(role, set())
    out: dict[str, str] = {}
    if role == "department":
        for key, value in ambient.items():
            if not value:
                continue
            if key in _DEPARTMENT_ENV_KEYS or key.startswith(_DEPARTMENT_ENV_PREFIXES):
                out[key] = value
    elif role in _AGENT_ROLES:
        out["PATH"] = coding_path(ambient.get("PATH", ""))
    else:
        if ambient.get("PATH"):
            out["PATH"] = ambient["PATH"]
    out["LOKAY_CAPABILITIES"] = ",".join(sorted(caps))
    return out


def authorize_effect(role: str, capability: str) -> dict:
    allowed = capability in ROLE_CAPABILITIES.get(role, set())
    if allowed:
        return {"allowed": True, "role": role, "capability": capability}
    return {
        "allowed": False,
        "route": "fail_closed",
        "reason": "capability_denied",
        "role": role,
        "capability": capability,
        "trace": True,
    }
