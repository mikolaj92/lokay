# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=329 -->

Repository: `mikolaj92/lokay`  
Issue: #329 — issue_to_pr: po on-goal commit/PR nie dokładaj off-goal na tej samej gałęzi

## Goal

`issue_to_pr` po on-goal commit i PR dalej pisze na tej samej gałęzi — off-goal.

## Files likely touched

- `factory_begin.py`
- `src/lokay/compose/issue_to_pr.py`

## Test plan

- On-goal commit + PR istnieje → drugi krok nie dodaje obcego pliku. Issue CLOSED → zero mutacji.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
