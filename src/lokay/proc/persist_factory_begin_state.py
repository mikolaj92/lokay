"""Persist one begin payload and one initial working ledger."""

from lokay.passkit import io as pass_io


def persist(workspace: dict, begin: dict, working: dict) -> dict:
    path = workspace["pass_dir"]
    pass_io.write_json(pass_io.begin_path(path), begin["begin"])
    pass_io.write_json(pass_io.working_path(path), working["working"])
    return {"ok": True, "pass_dir": path}
