# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=264 -->

Repository: `mikolaj92/lokay`  
Issue: #264 — reap i2pr/pi gdy issue CLOSED

## Goal

Po merge zostaje zywy i2pr/pi. #262 sprawia, ze mutex ich nie liczy, ale proces zyje dalej: pali lease, pi_budget, trzyma worktree.

## Files likely touched

- `src/lokay/proc/reap_over_budget.py`

## Test plan

- Live pid + issue CLOSED -> process na liscie reaped.
- Live pid + issue OPEN -> kept.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
