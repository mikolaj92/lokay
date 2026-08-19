# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=294 -->

Repository: `mikolaj92/lokay`  
Issue: #294 — closeout_pr: park gdy issue CLOSED, nie tylko po merge w tym przebiegu

## Goal

`closeout_pr` parkuje dopiero po własnym merge w tym przebiegu (#267). Harvest / Fixes# zamyka issue wcześniej, PR jeszcze otwarty albo closeout idzie inną route — etykiety zostają do następnego `survey_ready`.

## Files likely touched

- `src/lokay/proc/closeout_pr.py`

## Test plan

- PR open, issue CLOSED → park, route skip, bez merge.
- PR open, issue OPEN → bez zmian.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
