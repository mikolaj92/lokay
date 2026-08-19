# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=271 -->

Repository: `mikolaj92/lokay`  
Issue: #271 — issue_to_pr: nie wołaj repair_agent gdy localize puste

## Goal

Gdy `localize` padnie (puste ścieżki), `run_agent` odmawia (`localize_empty`), a `repair_agent` i tak pisze kod — byle łatanie czerwonego `test_local` — i mill merdżuje to jako Fixes #N.

## Files likely touched

- `src/lokay/compose/tick.py`

## Test plan

- localize puste → repair_agent nie odpalony.
- localize z ścieżkami → repair_agent jak dziś (czerwony test po prawdziwym patchu).

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
