"""Persist a launch-time repo lock collision as an explicit no-launch."""

from lokay.proc.record_dispatch_keep import apply as keep


def apply(*, pass_dir: str, candidate: dict) -> dict:
    return keep(pass_dir=pass_dir, candidate=candidate)
