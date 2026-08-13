"""Fala subprocess organ: dispatch one atom per process.

Routing lives in ``lokay.organ.*`` (one job family per module).
"""

from __future__ import annotations

import json
import os
from typing import Any

from fala import sdk

from lokay.git_commit import branch_ahead_of_upstream  # noqa: F401 — tests patch this
from lokay.organ.agent import handle_agent
from lokay.organ.common import (  # noqa: F401
    _conduction_values,
    _require_push,
    _require_real_diff,
    _require_test_local,
    _run_atom_main,
    _test_local_ok,
)
from lokay.organ.factory import handle_factory
from lokay.organ.implement import handle_implement
from lokay.organ.lanes import handle_lanes
from lokay.organ.recovery import handle_recovery
from lokay.organ.self_repair import handle_self_repair


def _handle(atom: str, inputs: dict[str, Any], up: dict[str, dict[str, Any]]) -> dict[str, Any]:
    from lokay.organ.common import _cfg_flags, _live_flags

    ctx = {
        "cfg": _cfg_flags(inputs),
        "live": _live_flags(inputs),
        "repo": str(
            inputs.get("repo")
            or up.get("get_issue", {}).get("issue", {}).get("repo")
            or ""
        ),
        "issue_number": None,
        "pr_number": None,
        "repair_mode": str(inputs.get("mode") or "") == "repair",
        "branch": str(
            inputs.get("branch")
            or up.get("make_branch", {}).get("branch")
            or up.get("worktree_add", {}).get("branch")
            or ""
        ),
    }
    issue_number = inputs.get("issue") or inputs.get("issue_number")
    if issue_number is None and "get_issue" in up:
        issue_number = up["get_issue"].get("issue", {}).get("number")
    ctx["issue_number"] = int(issue_number) if issue_number is not None else None
    pr_number = inputs.get("pr") or inputs.get("pr_number")
    ctx["pr_number"] = int(pr_number) if pr_number is not None else None

    for handler in (
        handle_recovery,
        handle_factory,
        handle_self_repair,
        handle_lanes,
        handle_implement,
        handle_agent,
    ):
        result = handler(atom, inputs, up, ctx)
        if result is not None:
            return result
    raise ValueError(f"unknown atom: {atom!r}")


def main() -> int:
    def handler(manifest: dict[str, Any]) -> dict[str, Any]:
        config = sdk.config(manifest)
        atom = str(config.get("atom") or manifest.get("process_id") or "")
        if not atom:
            raise RuntimeError("config.atom is required")
        if atom == "commit_all" and not os.environ.get("LOKAY_HEALTH_LEASE_PATH"):
            raise RuntimeError(
                "health lease path missing at Fala mutation boundary"
            )
        inputs = dict(sdk.declared_inputs(manifest))
        for key, value in sdk.input_values(manifest).items():
            if key not in sdk.INJECTED_INPUT_KEYS and key not in inputs:
                inputs[key] = value
        for key, value in config.items():
            if key == "atom":
                continue
            inputs.setdefault(key, value)
        up = _conduction_values(manifest)
        result = _handle(atom, inputs, up)
        ok_flag = bool(result.get("ok", False)) and result.get("_exit", 0) == 0
        if result.get("status") == "failed":
            ok_flag = False
        if not ok_flag and not result.get("skipped"):
            values = {"ok": False, "atom": atom, **{k: v for k, v in result.items() if k != "_exit"}}
            raise RuntimeError(json.dumps(values, ensure_ascii=False)[:2000])
        values = {"ok": True, "atom": atom, **{k: v for k, v in result.items() if k != "_exit"}}
        return sdk.output(values=values)

    return sdk.run_manifest_effector(handler)


if __name__ == "__main__":
    raise SystemExit(main())
