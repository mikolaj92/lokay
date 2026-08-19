# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=300 -->

Repository: `mikolaj92/lokay`  
Issue: #300 — daemon_cycle: SIGALRM w Fala native nie zrzuca lokay-daemon

## Goal

Strop 180s (#296) jest na main, ale SIGALRM leci w `native.host_run_package` (Fala). Handler rzuca `_PassCeiling` na stosie Mojo — Python nie łapie, `lokay-daemon` pada na gołym `Exception` bez komunikatu. `last-pass.json` nie dostaje `reason=pass_ceiling`. LaunchAgent kończy tick exit 1.

## Files likely touched

- `last-pass.json`
- `src/lokay/compose/daemon_cycle.py`

## Test plan

- Sygnał / sztuczny native-like Exception po stropie → payload `pass_ceiling`, proces nie pada. Krótki przebieg bez zmian.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
