# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=277 -->

Repository: `mikolaj92/lokay`  
Issue: #277 — organ: pass --issue to pr_merge

## Goal

#275 / PR 276 dodało `--issue` w `pr_merge.py` i park po merge. Organ tego nie podaje — park nigdy nie odpala.

## Files likely touched

- `pr_merge.py`
- `src/lokay/organ/lanes.py`
- `pr_merge.main`

## Test plan

- Znany issue → argv ma `--issue`.
- Brak issue → jak dziś, bez flagi.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
