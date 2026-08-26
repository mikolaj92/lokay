"""Attach the on-disk stuck ledger to begin and working envelopes. One job."""

from lokay.proc.factory_begin_receipt import with_stuck


def attach(begin: dict, working: dict, ledger: dict) -> dict:
    stuck = with_stuck({"stuck_path": ledger["stuck_path"]})["stuck"]
    payload = dict(begin.get("begin") or begin)
    work = dict(working.get("working") or working)
    payload["stuck"] = stuck
    work["stuck"] = stuck
    return {"ok": True, "begin": payload, "working": work}
