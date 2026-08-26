"""Parent step (4): triage; next issue same pass if no; issue_to_pr if yes."""

from __future__ import annotations


def triage(*, pass_dir: str, config_path: str | None, live: bool) -> dict:
    from lokay.proc.dispatch_triage_subflow import run as dispatch_triage
    from lokay.proc.queue_conflict_subflow import run as queue_conflict
    from lokay.proc.select_implement_subflow import run as select_implement
    from lokay.proc.survey_inbox_subflow import run as survey_inbox
    from lokay.proc.survey_ready_subflow import run as survey_ready

    inbox = survey_inbox(pass_dir=pass_dir, config_path=config_path, live=live)
    ready = survey_ready(pass_dir=pass_dir, config_path=config_path, live=live)
    dispatched = dispatch_triage(pass_dir=pass_dir, config_path=config_path, live=live)
    selected = select_implement(pass_dir=pass_dir)
    queued = queue_conflict(pass_dir=pass_dir, config_path=config_path, live=live)
    qroute = str(queued.get("route") or "")
    result = queued.get("result") if isinstance(queued.get("result"), dict) else {}
    if not qroute:
        qroute = str(result.get("route") or "")
    if not qroute and result.get("kept"):
        qroute = "ready"
    elif not qroute and (
        result.get("needs_human") or result.get("skipped") or result.get("demoted")
    ):
        qroute = "parked"
    qroute = qroute or "none"
    return {
        "ok": True,
        "route": "yes" if qroute == "ready" else "no",
        "pass_dir": pass_dir,
        "queue_route": qroute,
        "survey_inbox": inbox,
        "survey_ready": ready,
        "dispatch_triage": dispatched,
        "select_implement": selected,
        "queue_conflict": queued,
    }


def select_next(*, pass_dir: str, triage: dict) -> dict:
    from lokay.proc.advance_implementation_selection import run as advance

    recorded = dict(triage.get("queue_conflict") or {})
    recorded["route"] = str(triage.get("queue_route") or recorded.get("route") or "")
    if recorded.get("route") == "parked":
        recorded["route"] = "needs_human"
    out = advance(pass_dir=pass_dir, recorded=recorded)
    route = str(out.get("route") or "none")
    if route == "candidate":
        route = "yes"
    elif route == "ready":
        route = "yes"
    else:
        route = "no"
    return {**out, "ok": True, "route": route, "pass_dir": pass_dir}


def implement(
    *,
    pass_dir: str,
    config_path: str | None,
    live: bool,
    triage: dict,
    nxt: dict,
) -> dict:
    from lokay.proc.dispatch_implementation_subflow import run as dispatch

    if str(triage.get("route") or "") != "yes" and str(nxt.get("route") or "") != "yes":
        return {"ok": True, "route": "none", "skipped": True, "pass_dir": pass_dir}
    out = dispatch(pass_dir=pass_dir, config_path=config_path, live=live)
    return {**out, "ok": True, "route": "done", "pass_dir": pass_dir}


def back_to_prs(*, pass_dir: str, config_path: str | None, live: bool) -> dict:
    from lokay.proc.closeout_prs_subflow import run as closeout
    from lokay.proc.resolve_conflicts_subflow import run as conflicts

    resolved = conflicts(pass_dir=pass_dir, config_path=config_path, live=live)
    closed = closeout(pass_dir=pass_dir, config_path=config_path, live=live)
    return {
        "ok": True,
        "route": "prs",
        "pass_dir": pass_dir,
        "resolve_conflicts": resolved,
        "closeout_prs": closed,
    }
