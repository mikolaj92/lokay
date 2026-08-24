"""Read physical existence for configured checkout paths."""

from pathlib import Path


def read(config: dict) -> dict:
    missing = [
        f"{r['name']} → {r['clone_path']}"
        for r in config.get("repos", [])
        if r.get("enabled") and not Path(r["clone_path"]).exists()
    ]
    return {"ok": True, "missing_clones": missing}
