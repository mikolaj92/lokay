# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=298 -->

Repository: `mikolaj92/lokay`  
Issue: #298 — mill.lock busy: host-ff i tak, lock nie blokuje update main

## Goal

Gdy `mill.lock` jest zajęty, `lokay-mill-daemon.sh` pomija `lokay-host-ff`. Wiszący przebieg trzyma lock, main nie ląduje na dysku, nowy kod (np. #296) nie wchodzi do żywej maszyny.

## Files likely touched

- `mill.lock`
- `lokay-mill-daemon.sh`
- `scripts/lokay-mill-daemon.sh`

## Test plan

- Lock busy → host-ff wołany, daemon nie. Lock wolny → jak dziś.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
