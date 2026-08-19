# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=307 -->

Repository: `mikolaj92/lokay`  
Issue: #307 — mill-daemon: zapisz digest po pass_ceiling — nie reinstall co tick

## Goal

Po stropie 180s last-pass ma `health=pass_ceiling`. Skrypt młyna zapisuje digest checkoutu tylko gdy log ma health z listy (progress/idle/…). `pass_ceiling` nie ma. Digest nie ląduje → następny tick znowu `--reinstall-package lokay --reinstall-package fala` → znowu strop. Pętla.

## Files likely touched

- `scripts/lokay-mill-daemon.sh`

## Test plan

- Log z pass_ceiling → plik digest zapisany. Kolejny przebieg z tym samym digestem nie dodaje `--reinstall-package`.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
