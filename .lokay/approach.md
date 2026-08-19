# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=201 -->

Repository: `mikolaj92/lokay`  
Issue: #201 — repo mutex: zajęty też przez żywe issue_to_pr

## Goal

Przy #197 młyn odpalił drugi i2pr na #190 na tym samym repo. Mutex patrzy tylko na `pi`, nie na `compose.issue_to_pr`.

## Files likely touched

- `src/lokay/proc/repo_mutex.py`
- `tests/test_repo_mutex.py`

## Test plan

- Fixture `ps` z i2pr na `mikolaj92/lokay` → busy. Inne repo → nie busy.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
