from __future__ import annotations


from pathlib import Path
from types import SimpleNamespace



def _repo(name: str, *, enabled: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        clone_path=Path("/tmp") / name.split("/")[-1],
        priority=0,
        enabled=enabled,
        note="",
    )


