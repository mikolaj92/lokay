# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=315 -->

Repository: `mikolaj92/lokay`  
Issue: #315 — lokay-daemon: po pierwszym idle — exit, nie kręć max_passes

## Goal

Pusty katalog. Jeden survey już długi. LaunchAgent podaje `--max-passes 8`. compose kręci puste przebiegi aż `pass_ceiling` 180s.

## Files likely touched

- (infer from repo inspection)

## Test plan

- run_path idle przy max_passes=8 → jedno wywołanie, payload idle.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
