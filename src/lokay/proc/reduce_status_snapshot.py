"""Purely reduce read-only status facts into one snapshot."""


def reduce(
    config: dict,
    readiness: dict,
    clones: dict,
    lease: dict,
    receipt_fact: dict,
    work_fact: dict,
    repo_locks: dict,
    graphs: dict,
    preflight: dict,
) -> dict:
    repos = config.get("repos") or []
    receipt = receipt_fact.get("receipt")
    remaining = (receipt or {}).get("remaining") if isinstance(receipt, dict) else None
    remaining = (
        remaining if isinstance(remaining, dict) else {"note": "snapshot_unavailable"}
    )
    human = (
        (receipt or {}).get("human_residuals") if isinstance(receipt, dict) else None
    )
    by_repo = (
        remaining.get("by_repo") if isinstance(remaining.get("by_repo"), list) else []
    )
    notes = list(readiness.get("policy_notes") or [])
    missing = clones.get("missing_clones") or []
    if missing:
        notes.append(
            f"{len(missing)} missing clone(s) — implement blocked there; triage still runs"
        )
    work_units = list(work_fact.get("work_units") or [])
    return {
        "ok": True,
        "snapshot": {
            "kind": "status",
            "config": config.get("config"),
            "mode": config.get("mode"),
            "executor_enabled": config.get("executor_enabled"),
            "agent": config.get("agent"),
            "incident_repo": config.get("incident_repo"),
            "repos": [r["name"] for r in repos if r.get("enabled")],
            "repos_disabled": [r["name"] for r in repos if not r.get("enabled")],
            "repos_total": len(repos),
            "missing_clones": missing,
            "graphs": graphs.get("graphs") or [],
            "lokay_ready": readiness.get("lokay_ready"),
            "blockers": readiness.get("blockers") or [],
            "policy_notes": notes,
            "survey": False,
            "snapshot": True,
            "idle": None if receipt is None else receipt.get("idle"),
            "remaining": remaining,
            "survey_ok": None,
            "work_units": work_units,
            "latest_delivery": work_fact.get("latest_delivery"),
            "repo_locks": list(repo_locks.get("repo_locks") or []),
            "lease_ok": lease.get("lease_ok"),
            "lease_reason": lease.get("lease_reason"),
            "run_active": lease.get("run_active"),
            "run_observation_reason": lease.get("run_observation_reason"),
            "run_lease_path": lease.get("run_lease_path"),
            "preflight": preflight.get("preflight"),
            "merge_enabled": config.get("merge_enabled"),
            "require_checks": config.get("require_checks"),
            "require_llm_review": config.get("require_llm_review"),
            "max_issue_to_pr_per_pass": config.get("max_issue_to_pr_per_pass"),
            "k": config.get("max_issue_to_pr_per_pass"),
            "health": (receipt or {}).get("health") or "local",
            "by_repo": by_repo,
            "human_residuals": human,
            "last_pass": receipt,
            "description_error": graphs.get("description_error"),
        },
    }
