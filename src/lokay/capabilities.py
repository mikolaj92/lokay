"""Stable role capabilities independent of the selected harness."""
from __future__ import annotations

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

# Narrow GitHub identity for harnesses (builder/reviewer). Keep inherit_env=False;
# do not pass orchestration tokens beyond gh CLI identity.
_GITHUB_CREDENTIAL_KEYS = (
    "GH_TOKEN",
    "GITHUB_TOKEN",
    "GH_HOST",
    "GH_ENTERPRISE_TOKEN",
)

_AGENT_ROLES = frozenset({"builder", "reviewer"})


def executor_environment(role: str, ambient: Mapping[str, str]) -> dict[str, str]:
    caps = ROLE_CAPABILITIES.get(role, set())
    out: dict[str, str] = {}
    if ambient.get("PATH"):
        out["PATH"] = ambient["PATH"]
    if role in _AGENT_ROLES:
        for key in _GITHUB_CREDENTIAL_KEYS:
            value = ambient.get(key)
            if value:
                out[key] = value
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
