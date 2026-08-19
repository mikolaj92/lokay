# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=324 -->

Repository: `mikolaj92/lokay`  
Issue: #324 — reap_stale_worktrees: over_cap nie może trzymać całego stosu

## Goal

`reap_stale_worktrees`: gdy leftovers > `CLASSIFY_CAP` (4), cały stos dostaje `keep_stale_worktree` / `over_cap` i **nic nie spada**.

## Files likely touched

- `src/lokay/proc/reap_stale_worktrees.py`

## Test plan

- 5+ leftovers, issue CLOSED na najstarszych → max 4 reaped, nie 0. Żywe issue nietknięte.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
