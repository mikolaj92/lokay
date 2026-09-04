"""Select the explicit Lokay delivery scope from the configured catalog."""

from lokay.factory_scope import factory_repo, scoped_repos
from lokay.proc.pass_lane import self_repo


def select(config: dict) -> dict:
    repos, _ = scoped_repos(list(config.get("repos") or []), lokay=factory_repo())
    return {"ok": True, "repos": repos, "self_repo": self_repo(config)}
