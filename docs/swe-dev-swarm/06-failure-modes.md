# Failure modes and the handoff to a human

Child of #1551. Analysis only. No runtime change.

## What exists

src/lokay/stuck.py stores one row per repo and issue in stuck.json. record_failure counts misses. A transient reason gets a cooldown. A non-transient terminal miss stays active with no cooldown, and the issue leaves the slot once the bound is reached.

docs/WORKING.md names that bound. After enough unique-run misses for plan_only, zero_diff, or push_failed, the seed leaves the slot. At or above the bound the row is terminal. NEEDS_HUMAN and ai:needs-feedback are described as a rare residual after deterministic rules fail closed, not the default exit.

There is no design-round counter and no review-fix counter in this ledger. The keys are failure reasons from the factory, not Architect rounds or Fix rounds.

## Gap

SWE-Dev stops Design after 5 critic rounds and Review after 10 fix rounds, then a human takes the ticket. Lokay stops after a miss bound on delivery failures. It does not count design drafts or review-fix cycles, so it cannot hand those rounds to a person.

KEEP on an occupied PR is occupancy, not a stuck handoff. ai:needs-feedback exists as a label, and the product law tells the factory not to park ordinary work there.

## What not to pretend

The miss bound is not 5 and it is not 10. Copying those numbers into stuck.json would mix design rounds with push failures.

## Smallest later change

Add two counters beside the miss ledger, design_round and review_fix_round, each with its own cap. When a cap is hit, write one human residual and stop that issue. Leave the existing miss bound for plan_only, zero_diff, and push_failed.
