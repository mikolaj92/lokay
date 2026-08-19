# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=258 -->

Repository: `mikolaj92/lokay`  
Issue: #258 — fala_organ: live re-view before run_agent

## Goal

#256 / PR 257 dodało live re-view (`_issue_no_longer_open`) tylko dla `_MUTATING_ATOMS` = `commit_all`, `push`, `pr_create`, `pr_merge`.

## Files likely touched

- `src/lokay/fala_organ.py`
- `tests/test_fala_organ.py`
- `run_agent.main`

## Test plan

- `tests/test_fala_organ.py`: get_issue conduction OPEN, live re-view CLOSED → `run_agent.main` nie wołane, reason `issue_closed`. Analogicznie `repair_agent`.
- Nie ruszaj 180–192, 228, 235, 247, 253.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
