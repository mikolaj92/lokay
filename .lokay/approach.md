# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=245 -->

Repository: `mikolaj92/lokay`  
Issue: #245 — test: compileall tests+src (łap SyntaxError)

## Goal

#243: `test_global_pr_first.py` na main miał SyntaxError. test_local nie złapał, bo plik się nie kompilował w środku większego runu / merge poszedł mimo to. Kolejny popsuty test znowu zatruje main.

## Files likely touched

- `test_global_pr_first.py`
- `tests/test_suite_compiles.py`

## Test plan

- Sam plik: `pytest tests/test_suite_compiles.py` zielony.
- Nie ruszaj 180–192, 228, 235. Nie ruszaj tomli timeoutów.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
