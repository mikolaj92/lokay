"""Protected acceptance preparation and independent verification atoms."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lokay.acceptance import prepare_acceptance, verify_acceptance


def _ran_test_blob(blob: dict[str, Any]) -> bool:
    """True when upstream is a real test/repair result, not a skipped when-envelope."""
    if not blob:
        return False
    if blob.get("skipped") or blob.get("reason") in {
        "condition_not_met",
        "upstream_not_met",
    }:
        return False
    return (
        blob.get("passed") is not None
        or blob.get("tested") is not None
        or str(blob.get("route") or "")
        in {"pass", "fail", "terminal", "repaired", "publish"}
        or "decision" in blob
    )


def _test_observation(up: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Build kind=test observation without treating skipped repair as red."""
    final = up.get("finalize_local_tests") or {}
    selected = up.get("select_local_test") or {}
    # Acceptance-driven repair lands under acceptance_repair_execution.
    repair = (
        up.get("acceptance_repair_execution")
        or up.get("local_repair_execution")
        or {}
    )
    test = up.get("test_local_execution") or {}
    if final.get("route") == "publish" or selected.get("route") == "pass":
        ok = True
    elif selected.get("route") == "fail":
        ok = False
    elif _ran_test_blob(repair):
        ok = bool(repair.get("passed")) or (
            bool(repair.get("ok")) and bool(repair.get("tested"))
        )
    else:
        ok = bool(test.get("passed")) or (
            bool(test.get("ok")) and bool(test.get("tested"))
        )
    source = repair if _ran_test_blob(repair) else test
    ref = str(source.get("tests") or selected.get("tests") or "local-test")
    return {"kind": "test", "ok": ok, "ref": ref}


def handle_acceptance(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    if atom == "prepare_acceptance":
        issue = dict(up.get("get_issue", {}).get("issue") or {})
        root = Path.home() / ".lokay" / "acceptance"
        evidence = list(
            inputs.get("evidence")
            or [{"kind": "test", "expect": "declared repository tests pass"}]
        )
        return {"ok": True, **prepare_acceptance(issue, root=root, evidence=evidence)}
    if atom in {"verify_acceptance", "verify_acceptance_recheck"}:
        artifact = up.get("prepare_acceptance") or {}
        observation = _test_observation(up)
        try:
            verdict = verify_acceptance(
                str(artifact.get("path") or ""),
                [observation],
                str(artifact.get("digest") or ""),
            )
            # Always ok:true with route — same shape as select_local_test.
            # ok:false on accepted=false aborted the child (adapter_failed →
            # no_delivery) before route=repair could conduct local_repair.
            return {
                "ok": True,
                "atom": atom,
                **verdict,
                "accepted": bool(verdict.get("accepted")),
                "route": str(verdict.get("route") or "repair"),
            }
        except Exception as exc:
            # Digest/identity invalid is fail-closed, not a repair loop.
            return {
                "ok": False,
                "atom": atom,
                "accepted": False,
                "route": "fail_closed",
                "reason": "acceptance_invalid",
                "error": str(exc),
            }
    if atom == "finalize_acceptance":
        from lokay.proc.finalize_acceptance import finalize

        return finalize(
            up.get("verify_acceptance") or {},
            up.get("verify_acceptance_recheck") or {},
            up.get("acceptance_repair_execution") or {},
        )
    return None
