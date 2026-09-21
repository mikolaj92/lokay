"""Authorize the CLI closeout budget, not the daemon's durable receipt gate."""

import hashlib
import json
import re

from lokay.proc.review_repair_gate import route_review_repair


def authorize(gate: dict, source: dict, *, live: bool = True) -> dict:
    item = gate["inspected"]
    allowed = (
        live and source.get("route") == "repair"
        and bool(item.get("head"))
        and int(item.get("repair_budget") or 0) > 0
        and bool((item.get("policy") or {}).get("executor_enabled"))
    )
    review = dict(source.get("review") or {})
    handoff = {
        key: source.get(key, review.get(key, empty))
        for key, empty in (
            ("task", {}), ("findings", []), ("reviewed_head_sha", ""),
            ("task_identity_sha256", ""), ("review_result_sha256", ""),
        )
    }
    kind = str(source.get("repair_kind") or "")
    start = str(source.get("repair_start_head_sha") or "")
    if kind == "review":
        start = start or str(handoff["reviewed_head_sha"] or "")
        task = handoff["task"]
        valid = (
            route_review_repair({"decision": review}).get("route") == "repair"
            and all(handoff[key] == review.get(key) for key in handoff)
            and isinstance(task, dict) and task.get("repo") == item["repo"]
            and start == handoff["reviewed_head_sha"]
            and all(re.fullmatch(r"[a-f0-9]{64}", str(handoff[key] or ""))
                    for key in ("task_identity_sha256", "review_result_sha256"))
            and hashlib.sha256(json.dumps(
                task, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode()).hexdigest() == handoff["task_identity_sha256"]
        )
    else:
        valid = kind == "ci" and not any(handoff.values())
    valid = bool(valid and re.fullmatch(r"[a-f0-9]{40}", start))
    return {
        "ok": True,
        "route": "repair" if allowed and valid else "skip",
        "review": review,
        "repair_kind": kind,
        "repair_start_head_sha": start,
        **handoff,
        "step": str(source.get("step") or "pr_repair"),
    }
