# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=296 -->

Repository: `mikolaj92/lokay`  
Issue: #296 — daemon_cycle: strop przebiegu 180s — last-pass i exit, nie wisieć

## Goal

Przebieg młyna wisi. `last-pass.json` stoi, katalog pusty, LaunchAgent trzyma jeden PID, następny tick nie startuje.

## Files likely touched

- `last-pass.json`
- `mill-latest.log`
- `src/lokay/compose/daemon_cycle.py`
- `scripts/lokay-mill-daemon.sh`

## Test plan

- Sztucznie długi krok → po 180s receipt z `pass_ceiling`, proces kończy się. Krótki przebieg bez zmian.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
