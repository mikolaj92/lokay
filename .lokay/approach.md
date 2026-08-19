# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=199 -->

Repository: `mikolaj92/lokay`  
Issue: #199 — save_stuck: nie kasuj blocked z dysku

## Goal

Oil zablokował #190/#192 w stuck.json. Kolejny pass młyna zapisał ledger bez tych kluczy — młyn znowu wziął #190.

## Files likely touched

- `src/lokay/stuck.py`
- `tests/test_stuck.py`

## Test plan

- Plik ma blocked A. save bez A — A nadal na dysku.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
