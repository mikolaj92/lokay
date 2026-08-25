"""Select one explicit catalog slot that has stuck rows to check."""


def select(facts: dict, *, slot: int) -> dict:
    repos = list(facts.get("repos") or [])
    if slot < 1 or slot > len(repos):
        return {
            **facts,
            "harvest_slot": slot,
            "harvest_route": "empty",
            "harvest_repo": "",
        }
    repo = str(repos[slot - 1])
    prefix = f"{repo}#"
    has_rows = any(
        str(k).startswith(prefix) for k in (facts.get("stuck", {}).get("issues") or {})
    )
    return {
        **facts,
        "harvest_slot": slot,
        "harvest_route": "probe" if has_rows else "empty",
        "harvest_repo": repo,
    }
