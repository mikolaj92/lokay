"""Return the authored PR-repair terminal envelope."""


def summarize(*, final: dict, push: dict, repo: str, pr: int, branch: str) -> dict:
    published = final.get("route") == "publish" and push.get("ok") is True
    return {
        "ok": True,
        "result": {
            "repo": repo,
            "pr": pr,
            "branch": branch,
            "repaired": published,
            "published": published,
            "terminal": final.get("route"),
        },
    }
