"""Pure checks of publication evidence; no effects or process ordering."""
from __future__ import annotations
from typing import Any

def _test_local_ok(env: dict[str, Any] | None) -> bool:
    """Green suite, or an honest skip (no Python suite), counts as success.

    A recorded-red first probe (`ok: true, passed: false`) is NOT success —
    that envelope exists only so Fala can conduct the one-shot repair nest.
    """
    if not isinstance(env, dict) or not env:
        return False
    if env.get("route") == "pass":
        return True
    if env.get("passed") is False:
        return False
    if env.get("skipped") or env.get("reason") == "no_python_test_suite":
        return True
    return env.get("ok") is True

def _finalize_local_tests_ok(finalized: dict[str, Any] | None) -> bool:
    """Closed publish verdict from finalize_local_tests."""
    if not isinstance(finalized, dict) or not finalized:
        return False
    if finalized.get("route") == "publish":
        return True
    return _test_local_ok(finalized)

def _test_local_probe(up: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """First probe plus optional recheck. Missing probe is test_local_missing."""
    first = up.get("test_local")
    if first is None:
        first = up.get("test_local_execution")
    if first is None:
        return {
            "ok": False,
            "error": "refusing: test_local conduction missing",
            "reason": "test_local_missing",
        }
    recheck = up.get("test_local_recheck")
    # Fala emits a nonempty envelope for an unselected optional branch.
    if isinstance(recheck, dict) and recheck.get("reason") == "condition_not_met":
        recheck = None
    if not isinstance(recheck, dict) or not recheck:
        repair = up.get("local_repair_execution")
        if isinstance(repair, dict) and repair.get("route") in {
            "pass",
            "fail",
            "terminal",
        }:
            recheck = repair
        else:
            recheck = None
    if recheck is not None:
        if _test_local_ok(recheck):
            return None
        return {
            "ok": False,
            "error": str(
                recheck.get("error")
                or "refusing: test_local_recheck did not succeed"
            ),
            "reason": "test_local_recheck_failed",
        }
    if not _test_local_ok(first):
        return {
            "ok": False,
            "error": str(first.get("error") or "refusing: test_local did not succeed"),
            "reason": "test_local_failed",
        }
    return None

def _require_test_local(up: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """Fail-closed gate: push/pr_merge/pr_create need successful local tests.

    issue_to_pr_delivery conducts finalize_local_tests, not the raw probe,
    onto push/pr_create. That closed route is the verdict. Lanes without
    finalize still use the probe (and one bounded recheck when present).
    Missing finalize and missing test_local* fail closed. None means go.
    """
    finalized = up.get("finalize_local_tests")
    if isinstance(finalized, dict) and finalized:
        if _finalize_local_tests_ok(finalized):
            return None
        return {
            "ok": False,
            "error": str(
                finalized.get("error")
                or "refusing: finalize_local_tests did not publish"
            ),
            "reason": "test_local_failed",
        }
    return _test_local_probe(up)

def _require_push(up: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """Fail-closed gate: pr_create only after a successful push conduction.

    A red local suite or a refused/failed push must never reach
    `gh pr create`. None means go.
    """
    push = up.get("push")
    if push is None:
        return {
            "ok": False,
            "error": "refusing: push conduction missing",
            "reason": "push_missing",
        }
    if push.get("ok") is not True:
        return {
            "ok": False,
            "error": str(push.get("error") or "refusing: push did not succeed"),
            "reason": "push_failed",
        }
    return None

def _require_real_diff(up: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """Fail-closed gate: push/pr_create need a real (non-plan-only) diff.

    Plan/localize evidence (``.lokay/approach.md``, ``.lokay/localize.json``)
    is not progress. Missing key or ok:false returns an error envelope.
    None means go.
    """
    env = up.get("assert_real_diff")
    if env is None:
        return {
            "ok": False,
            "error": "refusing: assert_real_diff conduction missing",
            "reason": "real_diff_missing",
        }
    if env.get("ok") is not True:
        return {
            "ok": False,
            "error": str(env.get("error") or "refusing: diff is not real progress"),
            "reason": str(env.get("reason") or "plan_only"),
        }
    return None


def _require_acceptance(up: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """Fail-closed gate: when acceptance is in the path, it must accept (#1015).

    issue_to_pr_delivery prepares acceptance before the builder. If that
    artifact exists upstream, push/pr_create require verify_acceptance
    accepted — never delivered=true on a failed verdict.
    Paths without prepare_acceptance (e.g. pr_repair) skip this gate.
    None means go.
    """
    prepared = up.get("prepare_acceptance")
    if not isinstance(prepared, dict) or not prepared:
        return None
    verdict = (
        up.get("finalize_acceptance")
        or up.get("verify_acceptance_recheck")
        or up.get("verify_acceptance")
    )
    if not isinstance(verdict, dict) or not verdict:
        return {
            "ok": False,
            "error": "refusing: verify_acceptance conduction missing",
            "reason": "acceptance_missing",
            "accepted": False,
            "route": "fail_closed",
        }
    if verdict.get("accepted") is True or verdict.get("route") == "publish":
        return None
    return {
        "ok": False,
        "error": str(
            verdict.get("error")
            or verdict.get("reason")
            or "refusing: verify_acceptance did not accept"
        ),
        "reason": "acceptance_failed",
        "accepted": False,
        "route": "fail_closed",
        "failed_evidence": list(verdict.get("failed_evidence") or []),
    }

def _require_publish_gate(up: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """Fail-closed: push/pr_create need select_publish_gate route=publish.

    Unglues verify_acceptance from publish. Missing gate fails closed when
    assert_stamps_committed or verify_acceptance is present in the path.
    None means go (paths without the gate, e.g. pr_repair).
    """
    gate = up.get("select_publish_gate")
    if isinstance(gate, dict) and gate:
        if gate.get("route") == "publish" and gate.get("ok") is True:
            return None
        return {
            "ok": False,
            "error": str(
                gate.get("error")
                or gate.get("reason")
                or "refusing: select_publish_gate did not open publish"
            ),
            "reason": str(gate.get("reason") or "publish_gate_blocked"),
            "failed_atom": gate.get("failed_atom"),
        }
    # Transition: if stamps assert exists, require it even without select node.
    stamps = up.get("assert_stamps_committed")
    if isinstance(stamps, dict) and stamps:
        if stamps.get("ok") is True and stamps.get("route") == "publish":
            return None
        return {
            "ok": False,
            "error": str(
                stamps.get("error")
                or "refusing: Done-means stamp files dirty vs HEAD"
            ),
            "reason": str(stamps.get("reason") or "dirty_stamp_files"),
        }
    return None


