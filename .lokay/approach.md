# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=209 -->

Repository: `mikolaj92/lokay`  
Issue: #209 — testy: work:ready w mockach global_pr_first

## Goal

Po gate #193 suite: 12 czerwonych w `test_global_pr_first` / `test_autonomy_contracts`. Mocki issue bez `work:ready` nie przechodzą survey.

## Files likely touched

- `tests/test_global_pr_first.py`
- `tests/test_autonomy_contracts.py`

## Test plan

- `uv run --extra dev pytest -q tests/test_global_pr_first.py tests/test_autonomy_contracts.py` zielone.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
