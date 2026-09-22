"""Read-only delivery provenance checks; ancestry is never repair authority."""
from __future__ import annotations

import hashlib

from lokay.proc import pr_repair_receipts as receipts


def advance(provisional: dict, *, repo: str, pr: int, issue: int,
            viewed: dict, repair_receipt: dict, review: dict, tests: dict) -> dict:
    head = viewed.get("headRefOid")
    branch = viewed.get("headRefName")
    if (viewed.get("state") != "MERGED"
            or viewed.get("baseRefName") != "main"
            or provisional.get("work_id") != f"{repo}#{issue}"
            or (viewed.get("headRepository") or {}).get("nameWithOwner") != repo
            or not branch or provisional.get("branch") not in (None, branch)):
        raise ValueError("receipt_identity_mismatch")
    decision = review.get("decision") or {}
    task = decision.get("task") or {}
    if (review.get("ok") is not True or review.get("merge_ok") is not True
            or decision.get("verdict") != "approve" or decision.get("findings")
            or decision.get("reviewed_head_sha") != head
            or review.get("repo") != repo or review.get("pr") != pr
            or task.get("repo") != repo or task.get("number") != issue
            or task.get("type") != "Issue"
            or hashlib.sha256(receipts._canonical(task)).hexdigest() != decision.get("task_identity_sha256")
            or not receipts._HASH.fullmatch(str(decision.get("review_result_sha256") or ""))
            or tests.get("ok") is not True or tests.get("tested") is not True
            or tests.get("skipped") or tests.get("recorded_red")
            or tests.get("tested_head_sha") != head):
        raise ValueError("receipt_review_test_unverified")
    current = provisional["head_sha"]
    lineage = list(provisional.get("repair_lineage") or [])
    if current != head:
        if repair_receipt.get("repo") != repo or repair_receipt.get("pr") != pr:
            raise ValueError("receipt_identity_mismatch")
        entries = [*repair_receipt.get("checkpoint_history", []), {
            "checkpoint": repair_receipt.get("publication_checkpoint"),
            "terminal": repair_receipt.get("checkpoint_terminal"),
        }]
        for entry in entries:
            proof = entry.get("checkpoint") or {}
            intent = receipts._validate_intent(proof.get("intent"), repo=repo, pr=pr)
            if intent["start_head_sha"] != current:
                continue
            digest = hashlib.sha256(receipts._canonical({k: v for k, v in proof.items() if k != "sha256"})).hexdigest()
            repair_task = proof.get("task") or {}
            if (entry.get("terminal") != "confirmed_target"
                    or proof.get("sha256") != digest
                    or proof.get("schema") != "lokay.pr-repair-checkpoint/1"
                    or intent["branch"] != branch
                    or not (proof.get("evidence") or {}).get("repair")
                    or not (proof.get("evidence") or {}).get("test")
                    or not (proof.get("test") or {}).get("key")
                    or not (proof.get("run") or {}).get("run_id")):
                raise ValueError("receipt_repair_lineage_unverified")
            if intent["repair_kind"] == "review" and (
                repair_task.get("repo") != repo or repair_task.get("number") != issue
                or repair_task.get("type") != "Issue"
                or hashlib.sha256(receipts._canonical(repair_task)).hexdigest() != intent["task_identity_sha256"]
            ):
                raise ValueError("receipt_identity_mismatch")
            if intent["repair_kind"] == "ci":
                from lokay.stuck import issue_number_from_branch
                if issue_number_from_branch(branch) != issue:
                    raise ValueError("receipt_identity_mismatch")
            lineage.append({"start_head_sha": current, "target_head_sha": intent["target_head_sha"],
                            "checkpoint_sha256": digest, "intent_sha256": intent["intent_sha256"]})
            current = intent["target_head_sha"]
            if current == head:
                break
        if current != head:
            raise ValueError("receipt_identity_mismatch")
    return {**provisional,
            **({"original_head_sha": provisional.get("original_head_sha", provisional["head_sha"]),
                "repair_lineage": lineage} if lineage else {}),
            "head_sha": head, "branch": branch,
            "reviewer_session": (decision.get("review_evidence") or {}).get("run_id"),
            "reviewed_head_sha": head, "tested_head_sha": head,
            "review_result_sha256": decision["review_result_sha256"],
            "task_identity_sha256": decision["task_identity_sha256"],
            "test_run_ref": {k: tests.get(k) for k in ("db", "run_id", "path_id")}}
