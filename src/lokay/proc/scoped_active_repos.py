"""Apply the selected single-repo override to a catalog listing.

Empty override keeps the full enabled catalog. An override that is not an
enabled catalog member fails closed before any source is contacted.
"""

from __future__ import annotations

from lokay.factory_scope import factory_repo


class UnknownRepoScope(ValueError):
    """LOKAY_REPO_SCOPE names a repository this catalog does not deliver."""


def scoped_active_repos(cfg):
    repos = list(cfg.active_repos())
    target = factory_repo()
    if not target:
        return repos
    matched = [repo for repo in repos if repo.name == target]
    if not matched:
        raise UnknownRepoScope(target)
    return matched
