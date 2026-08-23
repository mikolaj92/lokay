"""Park one physically listed ready issue blocked by the durable ledger."""

from lokay.passkit.support import run_proc
from lokay.proc import unbounded_park


def park(classified: dict, *, config_path: str | None, live: bool) -> dict:
    issue = dict((classified.get("blocked") or [])[0])
    repo, number = str(classified["repo"]), int(issue["number"])
    argv = (
        (["--config", config_path] if config_path else [])
        + (["--live"] if live else [])
        + ["--repo", repo, "--issue", str(number)]
        + ([] if live else ["--dry-run"])
    )
    result = run_proc(unbounded_park.main, argv)
    return {
        "ok": True,
        "repo": repo,
        "issue": number,
        "applied": bool(result.get("ok") and result.get("applied")),
        "parked": result,
    }
