"""Write one verified green test cache receipt."""

from pathlib import Path
from lokay.test_cache import write_green


def write(inspected: dict, cached: dict, selected: dict) -> dict:
    if selected.get("route") != "green":
        return {"ok": True, "written": False, "tests": ""}
    source = dict(selected.get("source") or {})
    command = str(source.get("tests") or " ".join(inspected["test_argv"]))
    write_green(Path(inspected["worktree"]), str(cached["key"]), command)
    return {"ok": True, "written": True, "tests": command}
