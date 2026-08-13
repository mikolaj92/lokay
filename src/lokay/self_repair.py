"""Dedicated emergency recovery entrypoint; Fala owns all workflow order."""

from __future__ import annotations

import re
from typing import Any

from lokay.config import load_config
from lokay.graph_run import run_path
from lokay.preflight import trusted_fala_manifest
from lokay.state import append_event

_DEFAULT_INCIDENT_REPO = "mikolaj92/lokay"


def _incident_repo(cfg: Any) -> str:
    raw = getattr(cfg, "incident_repo", None)
    repo = str(raw or _DEFAULT_INCIDENT_REPO).strip()
    return repo if "/" in repo else _DEFAULT_INCIDENT_REPO


def _event(cfg: Any, **event: Any) -> None:
    try:
        append_event(cfg.state_path, {"kind": "self_repair", **event})
    except Exception:  # noqa: BLE001
        pass


def _incident_number(preflight: dict[str, Any], repo: str) -> int | None:
    pattern = re.compile(
        rf"^https://github\.com/{re.escape(repo)}/issues/(\d+)$"
    )
    match = pattern.fullmatch(str(preflight.get("incident_url") or ""))
    return int(match.group(1)) if match else None


def run_self_repair(
    config_path: str | None,
    preflight: dict[str, Any],
) -> dict[str, Any]:
    """Run exactly one bounded emergency Fala path, or fail closed."""
    cfg = load_config(config_path)
    repo = _incident_repo(cfg)
    issue = _incident_number(preflight, repo)
    result: dict[str, Any] = {
        "ok": False,
        "health": "self_repair_failed",
        "issue": issue,
        "incident_url": preflight.get("incident_url"),
        "gate_released": False,
    }
    fingerprint = str(preflight.get("fingerprint") or "")
    _event(cfg, phase="start", fingerprint=fingerprint, issue=issue)
    failed_names = {
        str(item.get("name"))
        for item in preflight.get("findings", [])
        if not item.get("ok")
    }
    if not preflight.get("carrier_ok"):
        result["reason"] = "carrier_unhealthy"
    elif issue is None or not fingerprint:
        result["reason"] = "deduplicated_incident_unavailable"
    elif failed_names & {"github_authentication", "executor_availability"}:
        result["reason"] = "bootstrap_dependency_unavailable"
    elif not cfg.executor_enabled:
        result["reason"] = "executor_disabled"
    else:
        try:
            path = run_path(
                path_id="self_repair",
                repo=repo,
                issue=issue,
                config_path=config_path,
                live=True,
                package_path=str(trusted_fala_manifest()),
                db_path=cfg.state_path.parent / "fala" / "self-repair",
                extra_inputs={
                    "fingerprint": fingerprint,
                    "failure_evidence": str(preflight.get("failure_evidence") or ""),
                    "incident": {
                        "repo": repo,
                        "number": issue,
                        "title": f"Preflight failure {fingerprint}",
                        "body": "Deterministic preflight incident; inspect current findings.",
                        "labels": [],
                        "assignees": [],
                        "url": str(preflight.get("incident_url") or ""),
                    },
                },
            )
        except Exception as exc:  # noqa: BLE001
            result.update(reason="fala_self_repair_failed", error=str(exc))
        else:
            result.update(path)
            result["health"] = (
                "restart_required" if path.get("ok") and path.get("restart_required")
                else "self_repair_failed"
            )
            if result.get("ok"):
                if result.get("gate_released") is not True and result.get("restart_required"):
                    result["gate_released"] = True
                flag = cfg.state_path.parent / "restart-required"
                try:
                    flag.write_text(str(result.get("commit") or "1"), encoding="utf-8")
                except OSError:
                    pass
                _event(
                    cfg,
                    phase="validated_restart_required",
                    issue=issue,
                    commit=result.get("commit"),
                )
                return result
            result["reason"] = result.get("reason") or "fala_self_repair_failed"
    _event(cfg, phase="failed", issue=issue, reason=result.get("reason"))
    return result
