# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=251 -->

Repository: `mikolaj92/lokay`  
Issue: #251 — test_global_pr_first: labels na issue, nie obok

## Goal

Na main `uv run --extra dev pytest -q` ma 6 faili. #243 naprawiło SyntaxError, ale w innych mockach `labels` nadal leżą *obok* `issues`, nie na issue. Intake widzi 0 ready → `len(intake) == 0`.

## Files likely touched

- `tests/test_autonomy_contracts.py`
- `tests/test_global_pr_first.py`

## Test plan

- Te 6 testów zielone. Nie osłabiać asercji.
- Nie ruszaj 180–192, 228, 235, 247.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
