# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=321 -->

Repository: `mikolaj92/lokay`  
Issue: #321 — daemon_cycle: pass_ceiling nie może wycierać remaining z last-pass

## Goal

`compose_daemon_cycle` przy `pass_ceiling` zapisuje last-pass jako `{ok, health, reason, ts, pass_ceiling_seconds}`. Gubi `remaining.by_repo` z przebiegu, który właśnie skończył survey.

## Files likely touched

- `src/lokay/compose/daemon_cycle.py`

## Test plan

- last-pass z `remaining.by_repo` → po pass_ceiling health=pass_ceiling i remaining.by_repo zostaje.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
