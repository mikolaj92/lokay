"""Invoke the authored detached-child harvest subflow."""


def harvest(config: dict, scope: dict, ledger: dict) -> dict:
    from lokay.proc.child_harvest_subflow import run

    return run(config, scope, ledger)
