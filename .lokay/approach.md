# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=215 -->

Repository: `mikolaj92/lokay`  
Issue: #215 — reap_over_budget: po kill over_budget — park + stuck plan_only

## Goal

`reap_over_budget` po `terminate_issue_to_pr_pid` stempluje receipt `reason=over_budget`, ale **nie** zdejmuje `work:ready`/`ai:ready` i **nie** zapisuje `stuck.json` (`plan_only`). Ticket wraca do survey.

## Files likely touched

- `stuck.json`
- `src/lokay/proc/reap_over_budget.py`
- `tests/test_reap_over_budget.py`

## Test plan

- `tests/test_reap_over_budget.py`
- W `test_reaps_over_budget_live_receipt`: po `run_reap_over_budget` zassertuj, że wywołano park dla `a/one#9` oraz `stuck` ma ten issue jako blocked/`plan_only` (mock `unbounded_park` / `record_failure`/`save_stuck`).
- Nie ruszaj 180–192.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
