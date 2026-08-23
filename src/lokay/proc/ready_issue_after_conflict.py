"""Apply the ready stage to one issue recovered from a conflict."""

from lokay.passkit.support import run_proc
from lokay.proc import stage_label


def apply(cleared: dict, *, config_path: str | None, live: bool) -> dict:
    argv = (
        (["--config", config_path] if config_path else [])
        + (["--live"] if live else [])
        + [
            "--repo",
            str(cleared["repo"]),
            "--issue",
            str(cleared["issue"]),
            "--stage",
            "ready",
        ]
    )
    result = run_proc(stage_label.main, argv)
    return {
        "ok": True,
        "applied": bool(result.get("ok") and result.get("applied")),
        "ready": result,
        **cleared,
    }
