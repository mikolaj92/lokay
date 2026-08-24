"""Build explicitly routed local-test terminal payloads."""


def inspection(inspected: dict) -> dict:
    return {"ok": True, "kind": "inspection", "result": inspected["result"]}


def cached(inspected: dict, cache: dict) -> dict:
    result = {
        "ok": True,
        "skipped": False,
        "tested": True,
        "cached": True,
        "worktree": str(inspected.get("worktree") or ""),
        "tests": str(
            (cache.get("cached") or {}).get("tests") or " ".join(inspected["test_argv"])
        ),
    }
    return {"ok": True, "kind": "cached", "result": result}


def green(inspected: dict, full: dict, scoped: dict, written: dict) -> dict:
    is_scoped = scoped.get("route") == "green"
    result = {
        "ok": True,
        "skipped": False,
        "tested": True,
        "cached": False,
        "scoped": is_scoped,
        "full_suite_returncode": full.get("returncode") if is_scoped else None,
        "worktree": str(inspected.get("worktree") or ""),
        "tests": written["tests"],
    }
    return {"ok": True, "kind": "green", "result": result}


def red(inspected: dict, full: dict, scoped: dict) -> dict:
    source = scoped if scoped.get("route") in {"red", "error"} else full
    result = {
        "ok": False,
        "error": source.get("error") or "local test suite failed",
        "returncode": source.get("returncode"),
        "worktree": str(inspected.get("worktree") or ""),
        "tests": source.get("tests") or " ".join(inspected["test_argv"]),
        "stdout_tail": source.get("stdout_tail", ""),
        "stderr_tail": source.get("stderr_tail", ""),
    }
    return {"ok": True, "kind": "red", "result": result}
