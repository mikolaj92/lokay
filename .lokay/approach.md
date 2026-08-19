# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=312 -->

Repository: `mikolaj92/lokay`  
Issue: #312 — mill-daemon: na starcie ticka odśwież mill-latest

## Goal

`lokay-mill-daemon.sh` czyści log na starcie (`: >LOG`), ale `mill-latest.log` kopiowane jest dopiero po `lokay-daemon`. Przez cały przebieg (do 180s) olej czyta stary ogon — np. poprzedni `pass_ceiling` — i diagnostyka kłamie.

## Files likely touched

- `lokay-mill-daemon.sh`
- `mill-latest.log`
- `scripts/lokay-mill-daemon.sh`

## Test plan

- Po host-ff, przed długim daemonem, mill-latest ma linię host-ff / current, nie stary pass_ceiling.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
