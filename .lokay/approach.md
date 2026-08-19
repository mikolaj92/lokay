# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=207 -->

Repository: `mikolaj92/lokay`  
Issue: #207 — select: zdejmij blocked z ready_by_repo

## Goal

Po #203 `test_blocked_ready_issue_is_not_selected_for_issue_to_pr` czerwony: skip jest, ale `ready_by_repo` dalej trzyma blocked.

## Files likely touched

- `src/lokay/proc/select_implement.py`
- `tests/test_select_implement.py`

## Test plan

- blocked w stuck → `ready_by_repo` puste dla tego repo. selected=0.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
