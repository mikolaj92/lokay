"""Fala bindings for explicit self-repair candidate validation."""

from typing import Any

SLOTS = 30


def _slot(atom):
    return int(atom.rsplit("_", 1)[1])


def handle_self_repair_validate(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    worktree = str(inputs.get("worktree") or "")
    base = str(inputs.get("base_sha") or "")
    subject = str(inputs.get("expected_subject") or "")
    commit = str(inputs.get("expected_commit") or "")
    if atom == "read_self_repair_candidate_state":
        from lokay.proc.read_self_repair_candidate_state import read

        return read(worktree=worktree, base_sha=base)
    if atom == "classify_self_repair_candidate_diff":
        from lokay.proc.classify_self_repair_candidate_diff import classify

        return classify(up.get("read_self_repair_candidate_state") or {})
    if atom == "validate_self_repair_identity_request":
        from lokay.proc.validate_self_repair_identity_request import validate

        return validate(
            up.get("classify_self_repair_candidate_diff") or {},
            expected_subject=subject,
            expected_commit=commit,
        )
    if atom == "inspect_self_repair_candidate_identity":
        from lokay.proc.inspect_self_repair_candidate_identity import inspect

        return inspect(up.get("validate_self_repair_identity_request") or {})
    if atom == "select_self_repair_identity_gate":
        inspected = up.get("inspect_self_repair_candidate_identity") or {}
        return (
            inspected
            if inspected.get("ok")
            else (up.get("validate_self_repair_identity_request") or {})
        )
    if atom == "verify_self_repair_candidate_identity":
        from lokay.proc.verify_self_repair_candidate_identity import verify

        return verify(up.get("select_self_repair_identity_gate") or {})
    if atom == "run_self_repair_tests":
        from lokay.proc.run_self_repair_tests import run_tests

        return run_tests(up.get("verify_self_repair_candidate_identity") or {})
    if atom == "list_self_repair_untracked_paths":
        from lokay.proc.list_self_repair_untracked_paths import list_paths

        return list_paths(up.get("run_self_repair_tests") or {}, slot_count=SLOTS)
    slot = _slot(atom) if atom.rsplit("_", 1)[-1].isdigit() else 0
    if atom.startswith("select_self_repair_untracked_"):
        from lokay.proc.select_self_repair_untracked_slot import select

        return select(up.get("list_self_repair_untracked_paths") or {}, slot=slot)
    if atom.startswith("check_self_repair_untracked_"):
        from lokay.proc.check_self_repair_untracked_path import check

        return check(up.get(f"select_self_repair_untracked_{slot}") or {})
    if atom.startswith("record_self_repair_untracked_"):
        from lokay.proc.record_self_repair_untracked_check import record

        return record(
            up.get(f"select_self_repair_untracked_{slot}") or {},
            up.get(f"check_self_repair_untracked_{slot}") or {},
        )
    if atom == "reduce_self_repair_untracked_checks":
        from lokay.proc.reduce_self_repair_untracked_checks import reduce_state

        return reduce_state(
            [
                up.get(f"record_self_repair_untracked_{i}") or {}
                for i in range(1, SLOTS + 1)
            ],
            up.get("list_self_repair_untracked_paths") or {},
        )
    if atom.startswith("check_self_repair_tracked_"):
        from lokay.proc.check_self_repair_tracked_diff import check

        kind = atom.removeprefix("check_self_repair_tracked_")
        source = {
            "working": "reduce_self_repair_untracked_checks",
            "cached": "check_self_repair_tracked_working",
            "committed": "check_self_repair_tracked_cached",
        }[kind]
        return check(up.get(source) or {}, kind=kind)
    if atom == "select_self_repair_committed_gate":
        return (
            up.get("check_self_repair_tracked_committed")
            or up.get("check_self_repair_tracked_cached")
            or {}
        )
    if atom == "recheck_self_repair_identity":
        from lokay.proc.recheck_self_repair_identity import recheck

        return recheck(up.get("select_self_repair_committed_gate") or {})
    if atom == "summarize_self_repair_validation":
        from lokay.proc.summarize_self_repair_validation import summarize

        return summarize(up.get("recheck_self_repair_identity") or {})
    return None
