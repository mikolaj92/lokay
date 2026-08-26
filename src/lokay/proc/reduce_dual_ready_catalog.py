"""Purely fold dual-ready probe rows into the wake set."""


def reduce_state(prepared: dict, rows: list[dict]) -> dict:
    wake: list[str] = []
    failed: list[str] = []
    for row in rows:
        repo = str(row.get("repo") or "")
        if not repo:
            continue
        if row.get("route") in {"wake", "failed"}:
            wake.append(repo)
        if row.get("route") == "failed":
            failed.append(repo)
    return {
        "ok": True,
        "wake_repos": sorted(set(wake)),
        "failed_repos": sorted(set(failed)),
        "probe_failed": bool(failed),
        "skipped": bool(prepared.get("recent_empty") or prepared.get("route") == "skip"),
    }


def apply_wake(prepared: dict, wake: dict) -> dict:
    return {
        **prepared,
        "active_repos": sorted(
            {str(name) for name in prepared.get("active_repos") or [] if str(name)}
            | {str(name) for name in wake.get("wake_repos") or [] if str(name)}
        ),
    }
