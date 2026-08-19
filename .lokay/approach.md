# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=205 -->

Repository: `mikolaj92/lokay`  
Issue: #205 — park: zdejmij też work:ready

## Goal

`unbounded_park` zdejmuje tylko `ai:ready`. Fail-closed (180–192) zostają w survey `work:ready` i młyn je zjada.

## Files likely touched

- `src/lokay/proc/unbounded_park.py`
- `tests/test_unbounded_park.py`

## Test plan

- argv zawiera `--remove-label work:ready` i `--remove-label ai:ready`.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
