"""Create and prune one factory-pass workspace directory."""

from pathlib import Path
from lokay.passkit import io as pass_io


def create(config: dict) -> dict:
    path = pass_io.make_pass_dir(Path(config["state_path"]))
    pass_io.prune_pass_dirs(Path(config["state_path"]), keep_path=path)
    return {"ok": True, "pass_dir": str(path)}
