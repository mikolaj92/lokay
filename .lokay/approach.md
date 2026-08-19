# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=279 -->

Repository: `mikolaj92/lokay`  
Issue: #279 — assert_real_diff: src poza localize = off-goal, fail-closed

## Goal

`assert_real_diff` uznaje każdy src za „real”. Pi/repair może wgrać obcy plik (nie z localize) i mill merdżuje to jako Fixes #N.

## Files likely touched

- `tick.py`
- `pr_finalize.py`
- `lokay/localize.json`
- `src/a.py`
- `src/b.py`

## Test plan

- localize=[src/a.py], diff src/a.py → real.
- localize=[src/a.py], diff src/b.py → off_goal.
- localize puste + tylko approach.md → plan_only.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
