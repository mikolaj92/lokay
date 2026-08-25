"""Run exactly one existing authored emergency self-repair graph."""

from pathlib import Path

from lokay.graph_run import run_path
from lokay.preflight import trusted_fala_manifest


def run(prepared: dict) -> dict:
    try:
        path = run_path(
            path_id="self_repair",
            repo=prepared["repo"],
            issue=int(prepared["issue"]),
            config_path=prepared.get("config_path") or None,
            live=True,
            package_path=str(trusted_fala_manifest()),
            db_path=Path(prepared["state_path"]).parent / "fala" / "self-repair",
            extra_inputs={
                "fingerprint": prepared["fingerprint"],
                "failure_evidence": prepared.get("failure_evidence") or "",
                "incident": {
                    "repo": prepared["repo"],
                    "number": prepared["issue"],
                    "title": f"Preflight failure {prepared['fingerprint']}",
                    "body": "Deterministic preflight incident; inspect current findings.",
                    "labels": [],
                    "assignees": [],
                    "url": str(prepared.get("incident_url") or ""),
                },
            },
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": True,
            "route": "terminal",
            "reason": "fala_self_repair_failed",
            "error": str(exc),
            "path": {},
        }
    return {"ok": True, "route": "classify", "path": path}
