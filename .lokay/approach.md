# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=310 -->

Repository: `mikolaj92/lokay`  
Issue: #310 — gh_issues: _list_open_issues przy 429 zwraca puste, nie raise

## Goal

#303 nauczył reap łapać GraphQL 429. #309 (owijka w list_ready) zdjęte jako klon. Źródło jest jedno: `_list_open_issues` woła `run_checked` i raise leci do survey. Każdy list_* (ready/inbox/labeled) pada.

## Files likely touched

- `src/lokay/gh_issues.py`

## Test plan

- Sztuczny 429 z run_checked → pusta lista, bez wyjątku. Inny błąd nadal raise.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
