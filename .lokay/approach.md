# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=239 -->

Repository: `mikolaj92/lokay`  
Issue: #239 — pr_create: skip when issue closed

## Goal

#235 zamknięte jako wontfix (klon timeoutów). Leftover pi i tak napisało src, mill otworzył i zmergował PR 237. Zamknięte issue nie może dostać PR.

## Files likely touched

- `src/lokay/proc/pr_create.py`
- `tests/test_pr_create.py`

## Test plan

- `tests/test_pr_create.py` (nowy):
- issue CLOSED → create_pr nie wołane, reason `issue_closed`.
- issue OPEN → create_pr jak dziś.
- Nie ruszaj tomli timeoutów. Nie ruszaj 180–192, 228, 235.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
