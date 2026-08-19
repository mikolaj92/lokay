# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=183 -->

Repository: `mikolaj92/lokay`  
Issue: #183 — Po merge occupancy musi spaść — ghost i2pr nie trzyma repo

## Goal

2026-08-19: po merge last-pass zostaje occupied przy issue_to_pr_started=0 / martwym pid. Ghost receipt zjada mutex.

## Files likely touched

- `src/lokay/proc/detach_issue_to_pr.py`
- `src/lokay/proc/refresh_occupancy.py`
- `tests/test_refresh_occupancy.py`

## Test plan

- Receipt z martwym pid → repo nie occupied. Żywy pid na otwartym issue → occupied. `uv run` test zielony.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
