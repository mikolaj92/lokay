"""Return the authored issue-delivery terminal envelope."""


def summarize(*, branch: dict, pr_create: dict, pr_label: dict, acceptance: dict | None = None) -> dict:
    """delivered=true only with a real PR *and* accepted verify_acceptance (#1015)."""
    pr = pr_create.get("pr") or pr_label.get("pr")
    acceptance = dict(acceptance or {})
    accepted = (
        acceptance.get("accepted") is True
        or (
            acceptance.get("ok") is True
            and str(acceptance.get("route") or "") == "publish"
        )
    )
    # Missing acceptance on an old path: fail closed (not delivered).
    if pr not in (None, "", 0) and not acceptance:
        return {
            "ok": False,
            "result": {
                "branch": branch.get("branch"),
                "pr": pr,
                "delivered": False,
                "reason": "acceptance_missing",
            },
        }
    if pr not in (None, "", 0) and not accepted:
        return {
            "ok": False,
            "result": {
                "branch": branch.get("branch"),
                "pr": pr,
                "delivered": False,
                "reason": "acceptance_failed",
                "failed_evidence": list(acceptance.get("failed_evidence") or []),
            },
        }
    delivered = pr not in (None, "", 0) and accepted
    return {
        "ok": True,
        "result": {
            "branch": branch.get("branch"),
            "pr": pr,
            "delivered": delivered,
        },
    }
