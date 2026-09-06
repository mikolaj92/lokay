"""Fail closed when Done-means stamp files remain dirty vs HEAD."""

from __future__ import annotations


def assert_clean(listed: dict) -> dict:
    dirty = list(listed.get("dirty_stamps") or [])
    if listed.get("route") == "dirty" or dirty:
        return {
            "ok": False,
            "route": "fail",
            "reason": "dirty_stamp_files",
            "error": "refusing: Done-means stamp files dirty vs HEAD: "
            + ", ".join(dirty),
            "dirty_stamps": dirty,
        }
    return {
        "ok": True,
        "route": "publish",
        "reason": "stamps_committed",
        "dirty_stamps": [],
    }
