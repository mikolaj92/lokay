# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=211 -->

Repository: `mikolaj92/lokay`  
Issue: #211 — dispatch: po plan_only blocked — park

## Goal

Fail-closed `plan_only` zostaje w survey `work:ready` (180–192). Park (#205) już zdejmuje etykietę, ale nikt go nie woła.

## Files likely touched

- `src/lokay/proc/dispatch_implement.py`
- `tests/test_dispatch_detach.py`

## Test plan

- Mock plan_only blocked → park wołany raz.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
