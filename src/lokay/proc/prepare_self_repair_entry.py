"""Prepare one closed self-repair incident identity and execution context."""

import re

from lokay.config import load_config

DEFAULT_REPO = "mikolaj92/lokay"


def prepare(*, config_path: str | None, preflight: dict) -> dict:
    cfg = load_config(config_path)
    raw = str(getattr(cfg, "incident_repo", None) or DEFAULT_REPO).strip()
    repo = raw if "/" in raw else DEFAULT_REPO
    match = re.fullmatch(
        rf"https://github\.com/{re.escape(repo)}/issues/(\d+)",
        str(preflight.get("incident_url") or ""),
    )
    issue = int(match.group(1)) if match else None
    failed = [
        str(x.get("name")) for x in preflight.get("findings", []) if not x.get("ok")
    ]
    return {
        "ok": True,
        "config_path": config_path or "",
        "state_path": str(cfg.state_path),
        "executor_enabled": cfg.executor_enabled,
        "repo": repo,
        "issue": issue,
        "fingerprint": str(preflight.get("fingerprint") or ""),
        "failure_evidence": str(preflight.get("failure_evidence") or ""),
        "incident_url": preflight.get("incident_url"),
        "carrier_ok": bool(preflight.get("carrier_ok")),
        "failed_names": failed,
    }
