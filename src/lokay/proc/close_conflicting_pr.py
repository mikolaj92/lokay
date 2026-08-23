"""Close one selected conflicting pull request."""

from lokay.passkit.support import run_proc
from lokay.proc import pr_close


def close(target: dict, *, config_path: str | None, live: bool) -> dict:
    argv = (
        (["--config", config_path] if config_path else [])
        + (["--live"] if live else [])
        + [
            "--repo",
            str(target["repo"]),
            "--pr",
            str(target["pr"]),
            "--comment",
            f"Lokay closed PR #{target['pr']}: mergeable={target['mergeable']}. Will re-implement from current main.",
        ]
    )
    result = run_proc(pr_close.main, argv)
    route = (
        "closed"
        if result.get("ok") and result.get("closed")
        else "planned" if result.get("ok") and result.get("planned") else "failed"
    )
    return {
        "ok": True,
        "route": route,
        "close": result,
        **target,
    }
