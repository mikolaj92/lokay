# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=259 -->

Repository: `mikolaj92/lokay`  
Issue: #259 — plan_only fail-closed: close issue (wontfix), nie tylko park etykiet

## Goal

Fail-closed plan_only zdejmuje work:ready/ai:ready (unbounded_park) i wpisuje stuck.json, ale nie zamyka issue.

## Files likely touched

- `src/lokay/proc/dispatch_implement.py`
- `src/lokay/proc/reap_over_budget.py`

## Test plan

- Plan_only failure -> close_issue.main wywołane z --repo i --issue.
- Stuck-blocked park (survey) -> close_issue NIE wywołane.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
