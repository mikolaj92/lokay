# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=193 -->

Repository: `mikolaj92/lokay`  
Issue: #193 — survey_ready: bez work:ready nie idź na i2pr

## Goal

Dziś młyn odpalał lokay#178 (tylko `ai:ready`, preflight) i zjadał mutex przy #183/#184. Alfred: survey `work:ready`. Produkty bez work:ready nie są kolejką.

## Files likely touched

- `src/lokay/proc/survey_ready.py`
- `tests/test_select_implement.py`

## Test plan

- Issue tylko `ai:ready` → skip. Issue z `work:ready`+`ai:ready` → ready.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
