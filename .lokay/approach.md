# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=273 -->

Repository: `mikolaj92/lokay`  
Issue: #273 — issue_to_pr: wyjdź gdy issue CLOSED po merge

## Goal

Po udanym merge (Fixes #N) wrapper `issue_to_pr` zostaje żywy i trzyma mutex. `reap_over_budget` (#264) ma zabić z zewnątrz na następnym przebiegu — ale ten sam przebieg, który merdżuje, jeszcze widzi i2pr jako started, a wrapper sam nie wychodzi.

## Files likely touched

- `compose/issue_to_pr.py`

## Test plan

- Issue CLOSED w trakcie i2pr → wrapper kończy (nie zostaje detached).
- Issue OPEN → jedzie jak dziś.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
