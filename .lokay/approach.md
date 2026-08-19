# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=231 -->

Repository: `mikolaj92/lokay`  
Issue: #231 — repair_agent Fala timeout 2100s → 480s (pi_budget)

## Goal

#229 ścięło `run_agent` do 480s. `repair_agent` (issue_to_pr, drugi strzał po teście) nadal ma `timeout_seconds = 2100` w `lokay.fala-package.toml`. Drugi coding slot zjada 35 min.

## Files likely touched

- `lokay.fala-package.toml`
- `fala/lokay.fala-package.toml`
- `src/lokay/data/lokay.fala-package.toml`
- `tests/test_graph.py`

## Test plan

- `tests/test_graph.py`: analogicznie do run_agent — repair_agent timeout == 480.
- Nie ruszaj 180–192, 228, 229.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
