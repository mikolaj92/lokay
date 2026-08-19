# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=229 -->

Repository: `mikolaj92/lokay`  
Issue: #229 — run_agent Fala timeout 2100s → 480s (pi_budget)

## Goal

`pi_budget` / `reap_over_budget` to 480s. W `lokay.fala-package.toml` effector `run_agent` ma `timeout_seconds = 2100`. Pi może pisać approach.md 35 min, a reap trzyma `coder_live`. Occupy stoi.

## Files likely touched

- `lokay.fala-package.toml`
- `src/lokay/data/lokay.fala-package.toml`
- `fala/lokay.fala-package.toml`
- `tests/test_fala_package_lock.py`
- `tests/test_graph.py`

## Test plan

- Istniejący test pakietu/grafu (np. `tests/test_fala_package_lock.py` / `tests/test_graph.py`): run_agent timeout == 480 (DEFAULT_BUDGET_S).
- Nie ruszaj 180–192 ani #228.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
