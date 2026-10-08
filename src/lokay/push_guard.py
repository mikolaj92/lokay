"""Decide whether a blueprint push can fast-forward."""


def push_allowed(*, remote_sha, expected_sha):
    if not remote_sha:
        return True
    return remote_sha == expected_sha
