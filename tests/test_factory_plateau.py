"""Contracts for authored product pass-budget evaluation."""

from lokay.proc.apply_product_leftover import apply
from lokay.proc.record_product_pass import record
from lokay.proc.classify_product_pass import classify as classify_pass
from lokay.proc.classify_product_plateau import classify as classify_plateau
from lokay.proc.decide_product_pass_stop import decide
from lokay.proc.finalize_product_pass import finalize


def evaluate(prepared, selected, tick, leftover, previous):
    applied = apply(tick, leftover)
    recorded = record(selected, applied, previous)
    classified = classify_pass(prepared, recorded)
    plateau = classify_plateau(classified)
    decided = decide(prepared, plateau)
    return finalize(prepared, decided)


def _prepared(**kw):
    return {"mode": "live", "live": True, "budget": 8, **kw}


def _tick(**kw):
    out = {
        "ok": True,
        "idle": False,
        "health": "progress",
        "progress": 1,
        "remaining": {"inbox": 1},
    }
    out.update(kw)
    return out


def test_idle_is_terminal():
    out = evaluate(
        _prepared(), {"slot": 1}, _tick(idle=True, health="idle", progress=0), {}, {}
    )
    assert out["route"] == "terminal" and out["payload"]["health"] == "idle"


def test_unchanged_work_becomes_plateau():
    previous = {
        "work_key": (1, 0, 0, 0, 0, 0, 0, 0, 0),
        "results": [],
        "total_progress": 1,
    }
    out = evaluate(_prepared(), {"slot": 2}, _tick(), {}, previous)
    assert (
        out["route"] == "terminal"
        and out["payload"]["health"] == "plateau"
        and out["payload"]["ok"] is False
    )


def test_unchanged_inflight_becomes_waiting():
    remaining = {"inbox": 0, "ready": 1, "issue_to_pr_started": 1}
    previous = {
        "work_key": (0, 1, 0, 0, 0, 0, 0, 0, 0),
        "results": [],
        "total_progress": 1,
    }
    out = evaluate(_prepared(), {"slot": 2}, _tick(remaining=remaining), {}, previous)
    assert out["payload"]["health"] == "waiting" and out["payload"]["ok"] is True


def test_hard_failure_stops():
    tick = {
        "ok": False,
        "idle": False,
        "health": "stall",
        "progress": 0,
        "remaining": {"ready": 1},
    }
    out = evaluate(_prepared(), {"slot": 1}, tick, {}, {})
    assert (
        out["route"] == "terminal"
        and out["payload"]["health"] == "stall"
        and out["payload"]["ok"] is False
    )


def test_dry_run_stops_after_one_pass():
    out = evaluate(_prepared(live=False), {"slot": 1}, _tick(), {}, {})
    assert out["route"] == "terminal" and out["payload"]["passes"] == 1


def test_last_budget_slot_is_terminal():
    out = evaluate(
        _prepared(budget=1), {"slot": 1}, _tick(remaining={"inbox": 2}), {}, {}
    )
    assert out["route"] == "terminal" and out["payload"]["passes"] == 1


def test_leftover_overflow_skip_does_not_count_as_progress():
    out = evaluate(
        _prepared(budget=1),
        {"slot": 1},
        _tick(progress=0, remaining={"ready": 1}),
        {
            "ok": True,
            "skipped": True,
            "leftover_skip": True,
            "reason": "leftover_overflow",
            "count": 200,
            "slot_count": 30,
        },
        {},
    )
    assert (
        out["payload"]["progress"] == 0
        and out["payload"]["leftover_skip"] is True
        and out["payload"]["reason"] == "leftover_overflow"
    )


def test_leftover_closeout_counts_progress():
    out = evaluate(
        _prepared(budget=1),
        {"slot": 1},
        _tick(progress=0, remaining={"ready": 1}),
        {"labels_removed": True, "leftover_closed": 1},
        {},
    )
    assert (
        out["payload"]["progress"] == 1
        and out["payload"]["remaining"]["issue_to_pr_started"] == 0
    )


def test_budget_overflow_fails_closed():
    from lokay.proc.prepare_product_budget import prepare

    assert (
        prepare(config_path=None, live=False, max_passes=9, slot_count=8)["ok"] is False
    )
