# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=254 -->

Repository: `mikolaj92/lokay`  
Issue: #254 — fala_organ: skip mutations when issue closed

## Goal

#239 zamyka tylko `pr_create`. Leftover i tak commituje i pushuje (#235, #247). Bramka per-atom to klon (253 zdjęte).

## Files likely touched

- `src/lokay/fala_organ.py`
- `organ/common.py`
- `tests/test_fala_organ.py`

## Test plan

- `tests/test_fala_organ.py`: issue CLOSED + atom `push` albo `pr_create` → nie woła create/push, reason `issue_closed`.
- Nie ruszaj 180–192, 228, 235, 247, 253.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
