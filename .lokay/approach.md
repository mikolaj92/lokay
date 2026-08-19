# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=262 -->

Repository: `mikolaj92/lokay`  
Issue: #262 — repo_mutex: nie busy gdy issue CLOSED

## Goal

Po merge issue zostaje i2pr/pi. repo_mutex widzi --issue N i trzyma repo occupied. Mill nie startuje nastepnego.

## Files likely touched

- `src/lokay/proc/repo_mutex.py`

## Test plan

- Fixture ps z --repo mikolaj92/lokay --issue 99, issue CLOSED -> busy false.
- To samo issue OPEN -> busy true.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
