"""Return the authored PR-repair terminal envelope."""


def summarize(
    *,
    final: dict,
    push: dict,
    repo: str,
    pr: int,
    branch: str,
    admit: dict | None = None,
) -> dict:
    """repaired/published only when tests publish *and* push succeeded (#1016).

    Admission skip for MERGED/CLOSED is a clean terminal (#1073).
    """
    admitted = dict(admit or {})
    if str(admitted.get("route") or "") == "skip":
        reason = str(admitted.get("reason") or "pr_already_merged")
        return {
            "ok": True,
            "result": {
                "repo": repo,
                "pr": pr,
                "branch": branch,
                "repaired": False,
                "published": False,
                "terminal": reason,
                "reason": reason,
                "skipped": True,
                "head_sha": "",
            },
        }
    tests_publish = final.get("route") == "publish"
    push_ok = push.get("ok") is True
    published = tests_publish and push_ok
    if tests_publish and not push_ok:
        return {
            "ok": False,
            "result": {
                "repo": repo,
                "pr": pr,
                "branch": branch,
                "repaired": False,
                "published": False,
                "terminal": "push_failed",
                "reason": str(push.get("reason") or "push_failed"),
                "head_sha": str(push.get("head_sha") or ""),
                "error": str(push.get("error") or ""),
            },
        }
    return {
        "ok": True,
        "result": {
            "repo": repo,
            "pr": pr,
            "branch": branch,
            "repaired": published,
            "published": published,
            "terminal": final.get("route"),
            "head_sha": str(push.get("head_sha") or ""),
        },
    }
