"""Create exactly one pull request after authored physical gates."""

from lokay.gh_prs import create_pr
from lokay.proc._common import runner


def create(request: dict, *, live: bool) -> dict:
    try:
        pull = create_pr(
            runner(),
            repo=request["repo"],
            title=request["title"],
            body=request["body"],
            head=request["head"],
            base=request["base"],
            live=live,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": True,
            "route": "terminal",
            "reason": "pr_create_failed",
            "error": str(exc),
        }
    return {"ok": True, "route": "created", "pull": pull, "planned": not live}
