# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=247 -->

Repository: `mikolaj92/lokay`  
Issue: #247 — list_inbox_issues: skip stuck blocked

## Goal

#236 filtruje w `list_inbox.py` *po* `list_inbox_issues`. Sam helper `src/lokay/gh_issues.py` `list_inbox_issues` nadal zwraca zablokowane (190–192 wracały do każdego callera).

## Files likely touched

- `list_inbox.py`
- `src/lokay/gh_issues.py`
- `lokay.stuck`
- `tests/test_gh_issues.py`
- `tests/test_list_inbox_issues.py`

## Test plan

- `tests/test_gh_issues.py` albo nowy `tests/test_list_inbox_issues.py`:
- zablokowane issue nie ląduje w wyniku.
- Nie ruszaj tomli timeoutów. Nie ruszaj 180–192, 228, 235.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
