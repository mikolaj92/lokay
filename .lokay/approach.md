# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=203 -->

Repository: `mikolaj92/lokay`  
Issue: #203 — select_implement: stuck blocked nie idzie na i2pr

## Goal

#192 było w stuck (blocked), a młyn i tak odpalił i2pr przy #201. `select_implement` nie czyta ledgera.

## Files likely touched

- `src/lokay/proc/select_implement.py`
- `tests/test_select_implement.py`

## Test plan

- Issue blocked w stuck → nie implementable. Issue bez blocked → jak dziś.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
