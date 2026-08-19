# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=289 -->

Repository: `mikolaj92/lokay`  
Issue: #289 — refresh_occupancy: żywy i2pr na CLOSED nie zajmuje repo

## Goal

Po harvest merge issue jest CLOSED, a leftover `issue_to_pr` jeszcze żyje. `refresh_occupancy` liczy żywe receipty jako occupied. Last-pass: occupied=true, ready=0, procesu już nie ma albo zombie na CLOSED. Następny ticket czeka na mutex.

## Files likely touched

- `src/lokay/proc/refresh_occupancy.py`

## Test plan

- Receipt żywy, issue CLOSED → occupied_repos bez tego repo, receipt w cleared.
- Receipt żywy, issue OPEN → occupied.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
