"""Host probe facts for D9. Does not call GitHub or git.

A red merge probe makes `ok` illegal in the same reading (#1627).
"""


def read_probes(raw):
    reasons = []
    if not raw.get("gh_auth", True):
        reasons.append("gh_auth")
    if not raw.get("pi_bin", True):
        reasons.append("pi_bin")
    canary = raw.get("decisions_canary") or {}
    if not canary.get("ok", True):
        reasons.append("decisions_canary")
    if not raw.get("gb10_up", True):
        reasons.append("gb10_up")
    if not raw.get("lease_table_ok", True):
        reasons.append("lease_table")
    merge_auth = raw.get("merge_auth") or {}
    if merge_auth.get("repos_without_push") or _expires_soon(merge_auth.get("token_expires_h")):
        reasons.append("merge_auth")
    merge_config = raw.get("merge_config") or {}
    if merge_config.get("resolved_off") or merge_config.get("missing"):
        reasons.append("merge_config")
    if raw.get("no_merge_alarm"):
        reasons.append("no_merge_alarm")
    if raw.get("verify_inconclusive"):
        reasons.append("verify_inconclusive")
    if raw.get("review_gate_suspect"):
        reasons.append("review_gate_suspect")
    head = raw.get("head_vs_origin") or {}
    return {
        "probes_green": not reasons and not raw.get("dirty") and not raw.get("stale_worktrees") and head.get("behind", 0) == 0 and head.get("ahead", 0) == 0,
        "hard_red": bool(reasons),
        "reasons": reasons,
        "behind": head.get("behind", 0),
        "ahead": head.get("ahead", 0),
        "dirty": bool(raw.get("dirty")),
        "lease_held": bool(raw.get("lease_held")),
        "stale_worktrees": list(raw.get("stale_worktrees") or []),
        "merge_illegal": "merge_auth" in reasons or "merge_config" in reasons,
        "canary_down": "decisions_canary" in reasons or "gb10_up" in reasons,
    }


def _expires_soon(hours):
    return hours is not None and hours < 72
