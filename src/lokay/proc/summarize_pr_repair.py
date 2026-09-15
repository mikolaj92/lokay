"""Return the authored PR-repair terminal envelope."""


def summarize(
    *,
    final: dict,
    push: dict,
    repo: str,
    pr: int,
    branch: str,
    admit: dict | None = None,
    repair_handoff: dict | None = None,
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
    handoff = dict(repair_handoff or {})
    task = handoff.get("task")
    findings = handoff.get("findings")
    repair_kind = str(handoff.get("kind") or "")
    start_head_sha = str(handoff.get("start_head_sha") or handoff.get("head_sha") or "").lower()
    if repair_kind not in {"ci", "review"}:
        return {
            "ok": False,
            "result": {
                "repo": repo, "pr": pr, "branch": branch,
                "repaired": False, "published": False,
                "terminal": "repair_kind_missing_or_invalid",
                "reason": "repair_kind_missing_or_invalid",
                "head_sha": str(push.get("head_sha") or ""),
            },
        }
    review_repair = repair_kind == "review"
    if published and repair_kind == "ci" and (
        not __import__("re").fullmatch(r"[a-f0-9]{40}", start_head_sha)
        or not __import__("re").fullmatch(r"[a-f0-9]{40}", str(push.get("head_sha") or "").lower())
        or str(push.get("head_sha") or "").lower() == start_head_sha
        or (task not in ({}, None)) or findings not in ([], None)
        or any(str(handoff.get(key) or "") for key in (
            "reviewed_head_sha", "task_identity_sha256", "review_result_sha256",
        ))
    ):
        return {
            "ok": False,
            "result": {
                "repo": repo, "pr": pr, "branch": branch,
                "repaired": False, "published": False,
                "terminal": "ci_repair_identity_invalid",
                "reason": "ci_repair_identity_invalid",
                "head_sha": str(push.get("head_sha") or ""),
            },
        }
    if published and review_repair and (
        not isinstance(task, dict) or not task
        or not isinstance(findings, list) or not findings
        or not str(handoff.get("reviewed_head_sha") or "")
        or not str(handoff.get("task_identity_sha256") or "")
        or not str(handoff.get("review_result_sha256") or "")
    ):
        return {
            "ok": False,
            "result": {
                "repo": repo, "pr": pr, "branch": branch,
                "repaired": False, "published": False,
                "terminal": "repair_handoff_incomplete",
                "reason": "repair_handoff_incomplete",
                "head_sha": str(push.get("head_sha") or ""),
            },
        }
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
            "terminal": "publish" if published else final.get("route"),
            "head_sha": str(push.get("head_sha") or ""),
            **({"repair_kind": "ci", "repair_start_head_sha": start_head_sha}
               if repair_kind == "ci" else {}),
            **({"repair_push_intent_sha256": str(push.get("repair_push_intent_sha256") or "")}
               if published and push.get("repair_push_intent_sha256") else {}),
            **({
                "task": task,
                "findings": findings,
                "repair_kind": repair_kind,
                "reviewed_head_sha": str(handoff.get("reviewed_head_sha") or ""),
                "task_identity_sha256": str(handoff.get("task_identity_sha256") or ""),
                "review_result_sha256": str(handoff.get("review_result_sha256") or ""),
            } if published and review_repair else {}),
        },
    }
