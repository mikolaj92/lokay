"""Build explicitly routed factory-begin terminal envelopes."""


def ready(config: dict, ledger: dict, workspace: dict, begin: dict) -> dict:
    result = {
        "ok": True,
        "pass_dir": workspace["pass_dir"],
        "live": bool(config.get("live")),
        "mode": config.get("mode"),
        "planned": begin["begin"]["planned"],
        "stuck_path": ledger["stuck_path"],
        "issue_count": int(ledger.get("issue_count") or 0),
        "offline": False,
    }
    return {"ok": True, "kind": "ready", "result": result}


def offline(config: dict, scope: dict) -> dict:
    result = {
        "ok": True,
        "mode": config.get("mode"),
        "live": bool(config.get("live")),
        "executed": False,
        "planned": [
            {
                "kind": "tick",
                "status": "survey",
                "repos": list(scope.get("repos") or []),
            }
        ],
        "actions": [],
        "idle": False,
        "remaining": {"note": "offline"},
        "health": "offline",
        "progress": 0,
        "offline": True,
    }
    return {"ok": True, "kind": "offline", "result": result}


def mode_not_live() -> dict:
    return {
        "ok": True,
        "kind": "mode_not_live",
        "result": {
            "ok": False,
            "error": "refusing --live while config mode is not live",
        },
    }


def preflight_failed() -> dict:
    return {
        "ok": True,
        "kind": "preflight_failed",
        "result": {
            "ok": False,
            "error": "preflight failed; product workflow blocked",
            "health": "preflight_failed",
            "executed": False,
            "progress": 0,
            "idle": False,
            "actions": [],
            "planned": [],
        },
    }
