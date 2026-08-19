# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=345 -->

Repository: `mikolaj92/lokay`  
Issue: #345 — commit_all: po on-goal src nie dodawaj plików poza localize

## Goal

#341: i2pr zrobił on-goal commit (`daemon_cycle.py` + test), potem w tym samym run `commit_all` (`git add -A`) dopisał `src/lokay/proc/factory_begin.py`. `assert_real_diff` odmówił (`off_goal`) — lokalny commit bez PR.

## Files likely touched

- `daemon_cycle.py`
- `src/lokay/proc/factory_begin.py`
- `src/lokay/proc/commit_all.py`
- `lokay/localize.json`
- `tests/test_commit_all.py`
- `factory_begin.py`

## Test plan

- `tests/test_commit_all.py` (albo istniejący)
- Worktree: on-goal plik z localize + obcy `factory_begin.py` → commit zawiera tylko localize, nie factory_begin.
- Nie ruszaj produktów. Nie klon 291/303/321/329/336/341.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
