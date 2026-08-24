"""Build one candidate from existing or explicit issue paths."""


def build(request: dict, inspected: dict, route: dict) -> dict:
    paths = (
        list(inspected.get("existing") or [])
        if route.get("route") == "existing"
        else list(
            dict.fromkeys(
                [*request.get("extras", []), *request.get("explicit_issue_paths", [])]
            )
        )
    )
    return {
        "ok": True,
        "route": "candidate",
        "paths": paths,
        "seed_paths": paths,
        "matched_tokens": [],
        "notes": [
            (
                "Existing localization evidence."
                if route.get("route") == "existing"
                else "Explicit issue file hints."
            )
        ],
        "source": "existing" if route.get("route") == "existing" else "bypass",
    }
