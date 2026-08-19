# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=317 -->

Repository: `mikolaj92/lokay`  
Issue: #317 — closeout_pr: atom >100 linii, test_local czerwony na main

## Goal

`src/lokay/proc/closeout_pr.py` ma 108 linii na `origin/main`. `tests/test_closeout_pr.py::test_closeout_pr_is_thin_glue` wymaga `<= 100`. Każdy `issue_to_pr` pada na `test_local`, potem pi „naprawia” closeout jako przyczepkę do obcego ticketu.

## Files likely touched

- `src/lokay/proc/closeout_pr.py`
- `lokay.closeout`

## Test plan

- `test_closeout_pr_is_thin_glue` zielony. `len(splitlines()) <= 100` zostaje.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
