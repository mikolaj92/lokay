# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=197 -->

Repository: `mikolaj92/lokay`  
Issue: #197 — testy: dual work:ready+ai:ready po gate #193

## Goal

Po #193/#194 `survey_ready` wymaga `work:ready`. Suite na main: 18 czerwonych (`test_intake_mill_gate`, `test_autonomy_contracts`, `test_global_pr_first`) — mocki mają tylko `ai:ready`.

## Files likely touched

- `survey_ready.py`
- `tests/test_intake_mill_gate.py`
- `tests/test_autonomy_contracts.py`
- `tests/test_global_pr_first.py`

## Test plan

- `uv run --extra dev pytest -q tests/test_intake_mill_gate.py tests/test_autonomy_contracts.py tests/test_global_pr_first.py` zielone.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
