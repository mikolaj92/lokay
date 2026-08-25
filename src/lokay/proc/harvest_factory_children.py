"""Invoke the authored detached-child harvest subflow."""


def harvest(config: dict, scope: dict, ledger: dict) -> dict:
    from lokay.proc.child_harvest_subflow import run
    from lokay.proc.factory_begin_receipt import harvest_receipt, with_stuck

    return harvest_receipt(run(config, scope, with_stuck(ledger)))
