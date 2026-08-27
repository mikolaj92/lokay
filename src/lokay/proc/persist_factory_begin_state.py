"""Write begin.json. One file, one job."""

from lokay.passkit import io as pass_io


def persist(workspace: dict, begin: dict) -> dict:
    path = workspace["pass_dir"]
    payload = dict(begin.get("begin") or begin)
    pass_io.write_json(pass_io.begin_path(path), payload)
    return {"ok": True, "pass_dir": path}
