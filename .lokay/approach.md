# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=213 -->

Repository: `mikolaj92/lokay`  
Issue: #213 — survey_ready: stuck blocked → park

## Goal

Dispatch parkuje nowe plan_only (#211). Stare blocked zostają w `work:ready` i zaśmiecają survey.

## Files likely touched

- `src/lokay/proc/survey_ready.py`
- `tests/test_survey_list.py`

## Test plan

- Mock blocked w stuck + listed ready → park wołany, nie ma w implementable.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
