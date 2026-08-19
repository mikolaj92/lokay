# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=181 -->

Repository: `mikolaj92/lokay`  
Issue: #181 — Stare .lokay-preserved nie może zjadać worktree_add

## Goal

Influenzer#177 (2026-08-19): `worktree_add` padło `worktree preservation archive already exists`. Sztuka zjedzona, restart ręczny (rm archive / prune). Katalog `.lokay-preserved` zostaje po starych przebiegach i blokuje następną.

## Files likely touched

- `src/lokay/git_worktree.py`
- `tests/test_worktree_reset.py`

## Test plan

- `tests/test_worktree_reset.py`: live worktree + istniejące `.corner.lokay-preserved` z `valuable` → remove ok, stare `valuable` nienaruszone, nowy `.corner-2.lokay-preserved` ma snapshot. Istniejący test `fails_closed_on_interrupted_preservation_archive` (brak live path) zostaje.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
