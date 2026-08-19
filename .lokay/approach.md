# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=305 -->

Repository: `mikolaj92/lokay`  
Issue: #305 — process_exit_code: pass_ceiling to exit 0

## Goal

Strop przebiegu zapisuje last-pass `reason=pass_ceiling` / `ok=false` (#296/#300), ale `process_exit_code` nie zna tego health i zwraca 1. LaunchAgent traktuje tick jak crash (`last exit 1`).

## Files likely touched

- `src/lokay/envelope.py`

## Test plan

- Payload `health=pass_ceiling` / `reason=pass_ceiling` → kod 0. Inny `ok=false` bez produkcji → 1.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
