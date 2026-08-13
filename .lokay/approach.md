# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=70 -->

Repository: `mikolaj92/lokay`  
Issue: #70 — [canary] mill smoke: add docs/MILL_SMOKE.md with operator live commands

## Goal

Operator-authored smoke ticket. Trust this issue: implement it; do not park as NEEDS_HUMAN.

## Files likely touched

- `docs/MILL_SMOKE.md`
- `config.live-autonomous.example.yaml`
- `config.yaml`
- `scripts/lokay-mill-daemon.sh`
- `docs/AUTONOMY.md`
- `docs/WORKING.md`

## Test plan

- Run the smallest useful tests for files touched

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
