"""Select the explicit Lokay delivery scope from the configured catalog."""

from lokay.mill_scope import mill_repo, scoped_repos
from lokay.proc.pass_lane import self_repo


def select(config: dict) -> dict:
    repos, _ = scoped_repos(list(config.get("repos") or []), mill=mill_repo())
    return {"ok": True, "repos": repos, "self_repo": self_repo(config)}
