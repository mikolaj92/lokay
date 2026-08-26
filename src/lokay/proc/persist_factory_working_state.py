"""Write working.json. One file, one job."""

from lokay.passkit import io as pass_io


def persist(workspace: dict, working: dict) -> dict:
    path = workspace["pass_dir"]
    work = dict(working.get("working") or working)
    pass_io.write_json(pass_io.working_path(path), work)
    return {"ok": True, "pass_dir": path}
