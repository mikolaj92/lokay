# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=281 -->

Repository: `mikolaj92/lokay`  
Issue: #281 — stage_label: nie nakładaj ai:ready na CLOSED

## Goal

Po merge (Fixes #N) issue jest CLOSED i park zdejmuje ready. Potem `stage_label` / leftover i2pr znowu kładzie `ai:ready` na zamknięty ticket.

## Files likely touched

- `src/lokay/proc/stage_label.py`

## Test plan

- CLOSED + stage ready → etykiet nie dodano.
- OPEN → jak dziś.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
