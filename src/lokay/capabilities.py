"""Stable role capabilities independent of the selected harness."""
from __future__ import annotations

import os
from importlib.resources import files
from typing import Mapping

ROLE_CAPABILITIES = {
    "builder": {"code.write"},
    "reviewer": {"evidence.read", "verdict.propose"},
    "acceptance_effect": {"acceptance.write"},
    "push_effect": {"git.push"},
    "merge_effect": {"pr.merge"},
    "close_effect": {"issue.close"},
    "pr_effect": {"pr.create"},
}

_AGENT_ROLES = frozenset({"builder", "reviewer"})

# Coding/review harnesses must not receive GitHub identity (#1008 was a bandage).
_GITHUB_CREDENTIAL_KEYS = (
    "GH_TOKEN",
    "GITHUB_TOKEN",
    "GH_HOST",
    "GH_ENTERPRISE_TOKEN",
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
    caps = ROLE_CAPABILITIES.get(role, set())
    out: dict[str, str] = {}
    if role in _AGENT_ROLES:
        out["PATH"] = coding_path(ambient.get("PATH", ""))
        # Explicitly do not forward GitHub credentials into the harness.
        for key in _GITHUB_CREDENTIAL_KEYS:
            out.pop(key, None)
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
