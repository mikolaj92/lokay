"""Build one bounded localization-agent prompt and validation facts."""

from lokay.localize import extract_seed_paths
from lokay.localize_agent import localize_prompt


def build(request: dict, inspected: dict, route: dict) -> dict:
    if route.get("route") != "agent":
        return {
            "ok": True,
            "route": "unused",
            "prompt": "",
            "tree": inspected.get("tree") or [],
            "seed_paths": [],
            "extras": [],
        }
    prompt = localize_prompt(
        seed_text=request["seed"],
        tree_sample=inspected.get("tree") or [],
        extra_paths=request.get("extras") or [],
        max_paths=request["max_paths"],
    )
    return {
        "ok": True,
        "route": "agent",
        "prompt": prompt,
        "tree": inspected.get("tree") or [],
        "seed_paths": list(extract_seed_paths(request["seed"])),
        "extras": request.get("extras") or [],
    }
