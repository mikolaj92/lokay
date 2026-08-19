# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=243 -->

Repository: `mikolaj92/lokay`  
Issue: #243 — test_global_pr_first.py: SyntaxError na main

## Goal

`tests/test_global_pr_first.py` na main nie kompiluje się. Linia 75: brak przecinka / popsuty dict po #209.

## Files likely touched

- `tests/test_global_pr_first.py`

## Test plan

- `python3 -m py_compile tests/test_global_pr_first.py` wychodzi 0.
- Nie ruszaj 180–192, 228, 235.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
