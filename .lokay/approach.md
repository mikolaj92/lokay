# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=97 -->

Repository: `mikolaj92/lokay`  
Issue: #97 — Tick z aktualnego main, albo fail-closed gdy host z tyłu

## Goal

Lokaj na mini jedzie starym `main` po merge. Merge wstał, host nadal na starym HEAD — bramki z merga nie żyją (pr_create po czerwonym `test_local`, jak #89/#96).

## Files likely touched

- `repos.mikolaj92.yaml`

## Test plan

- Run the smallest useful tests for files touched

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
