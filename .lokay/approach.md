# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=235 -->

Repository: `mikolaj92/lokay`  
Issue: #235 — test_local Fala timeout 2100s → 300s

## Goal

`run_agent`/`repair_agent`/`self_repair_run_agent` są na 480s. `test_local` w `lokay.fala-package.toml` nadal ma `timeout_seconds = 2100`. Po src i2pr wisi do 35 min na pytest — cykl 5–10 min pada, PR nie powstaje.

## Files likely touched

- `lokay.fala-package.toml`
- `fala/lokay.fala-package.toml`
- `src/lokay/data/lokay.fala-package.toml`
- `tests/test_graph.py`

## Test plan

- `tests/test_graph.py`: każdy `test_local` ma timeout == 300.
- Nie ruszaj 180–192, 228.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
