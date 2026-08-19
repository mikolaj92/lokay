# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=224 -->

Repository: `mikolaj92/lokay`  
Issue: #224 — plan_pass: stuck blocked — nie wstawiaj do triage_targets

## Goal

`dispatch_triage` (#222) już skipuje `blocked` w stuck.json. `plan_pass` nadal pakuje te issue do `triage_targets` z inboxu — zjada `triage_budget` i woła intake, które maluje z powrotem `ai:ready` (190–192).

## Files likely touched

- `src/lokay/proc/plan_pass.py`
- `tests/test_plan_pass.py`

## Test plan

- Nowy `tests/test_plan_pass.py`: inbox ma blocked + zwykły; w planie tylko zwykły.
- Nie ruszaj 180–192.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
