# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=68 -->

Repository: `mikolaj92/lokay`  
Issue: #68 — Preflight failure 3c656f93985e9107

## Goal

<!-- lokay-preflight:3c656f93985e9107 -->
Bounded checks failed: Confirmed in 4 of 5 daemon runs. Repeated product failure evidence:

## Files likely touched

- `src/lokay/proc/select_implement.py`
- `tests/test_global_pr_first.py`

## Test plan

- Verify a manual-only PR does not block ready work in the same repository
- Run global PR-first and mill-health tests

## Non-goals

- Changing backpressure from actionable AI PRs
- Treating manual / `ai:needs-review` PRs as automatic work

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- No explicit file paths in issue; infer from repo inspection.
