# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=283 -->

Repository: `mikolaj92/lokay`  
Issue: #283 — survey_ready: CLOSED przy live re-view — park, nie i2pr

## Goal

`survey_ready` ufa liście OPEN. W tym samym przebiegu merge zamyka ticket, a last-pass wciąż ma ready=1 / i2pr_started=1 i może odpiąć sibling albo zostawić etykiety.

## Files likely touched

- `src/lokay/proc/survey_ready.py`

## Test plan

- Lista ma CLOSED + work:ready → park, remaining_ready bez niego.
- OPEN + work:ready → jak dziś.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
