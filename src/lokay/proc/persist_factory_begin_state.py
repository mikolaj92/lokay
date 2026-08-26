"""Persist one begin payload and one initial working ledger."""

from lokay.passkit import io as pass_io
from lokay.proc.factory_begin_receipt import with_stuck
from lokay.proc.seed_prior_catalog import seed


def persist(workspace: dict, begin: dict, working: dict) -> dict:
    path = workspace["pass_dir"]
    payload = dict(begin["begin"])
    work = dict(working["working"])
    stuck = with_stuck({"stuck_path": payload["stuck_path"]})["stuck"]
    payload["stuck"] = stuck
    work["stuck"] = stuck
    work = seed(working=work, begin=payload, pass_dir=path)
    pass_io.write_json(pass_io.begin_path(path), payload)
    pass_io.write_json(pass_io.working_path(path), work)
    return {"ok": True, "pass_dir": path}
