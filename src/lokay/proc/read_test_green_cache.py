"""Read one exact test cache key for the declared command and current git identity."""

from pathlib import Path
from lokay.proc._common import runner
from lokay.test_cache import cache_key, read_green


def read(inspected: dict) -> dict:
    if inspected.get("route") != "test":
        return {"ok": True, "route": "terminal", "key": "", "cached": {}}
    run = runner()
    root = Path(inspected["worktree"])
    argv = tuple(inspected["test_argv"])
    key = cache_key(run, root, argv)
    cached = read_green(root, key)
    return {
        "ok": True,
        "route": "hit" if cached is not None else "miss",
        "key": key,
        "cached": cached or {},
    }
