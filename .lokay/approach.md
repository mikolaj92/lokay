# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=291 -->

Repository: `mikolaj92/lokay`  
Issue: #291 — reap: TERM i2pr gdy issue CLOSED, nie czekaj 8 min

## Goal

#289 czyści receipt i occupancy, ale leftover `issue_to_pr` na CLOSED dalej żyje do reap over-budget (8 min). Palimy pi i trzymamy worktree.

## Files likely touched

- `src/lokay/proc/refresh_occupancy.py`

## Test plan

- Receipt żywy, issue CLOSED, pid mock → kill + cleared. OPEN → bez kill.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
