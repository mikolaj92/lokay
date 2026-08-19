# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=267 -->

Repository: `mikolaj92/lokay`  
Issue: #267 — closeout: zdejmij work:ready/ai:ready gdy issue CLOSED

## Goal

Po merge (Fixes #N) issue jest CLOSED, ale zostaja work:ready i ai:ready.

## Files likely touched

- `src/lokay/proc/closeout_pr.py`

## Test plan

- Issue CLOSED z etykietami ready -> park/remove-label wywolane.
- Issue OPEN -> etykiet nie ruszac.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
