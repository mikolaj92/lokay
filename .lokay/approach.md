# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=256 -->

Repository: `mikolaj92/lokay`  
Issue: #256 — fala_organ: live re-view issue before mutate

## Goal

#254 bramkuje mutacje na `up.get_issue` z **początku** i2pr. Ticket zamknięty w locie (235, 247) nadal wygląda OPEN. W `organ/common.py` jest już `_issue_no_longer_open` (live re-view). Organ jej nie woła.

## Files likely touched

- `organ/common.py`
- `src/lokay/fala_organ.py`
- `tests/test_fala_organ.py`

## Test plan

- `tests/test_fala_organ.py`: get_issue conduction OPEN, live re-view CLOSED → push/pr_create nie wołane, reason `issue_closed`.
- Nie ruszaj 180–192, 228, 235, 247, 253.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
