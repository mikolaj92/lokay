# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=248 -->

Repository: `mikolaj92/lokay`  
Issue: #248 — pr_create: body Fixes #<issue>

## Goal

#236 zmergowane (PR 238), issue zostało OPEN — body PR nie miało `Fixes #<n>`. Mill nie zamyka ticketu po merge.

## Files likely touched

- `src/lokay/proc/pr_create.py`

## Test plan

- Test pr_create/organ: body zawiera `Fixes #7` (albo dany numer).
- Nie ruszaj tomli timeoutów. Nie ruszaj 180–192, 228, 235, 236, 247.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
