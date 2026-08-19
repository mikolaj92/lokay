# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=331 -->

Repository: `mikolaj92/lokay`  
Issue: #331 — issue_to_pr: 429/survey fail nie jest stopem dostarczenia

## Goal

#329: `_delivery_stop_reason` gdy `gh issue view` / `gh pr list` zwraca None (GraphQL 429) → `delivery_survey_unavailable` → `compose_issue_to_pr` **ok + stopped**. Fabryka traktuje to jak dostarczenie i nie jedzie.

## Files likely touched

- `src/lokay/compose/issue_to_pr.py`

## Test plan

- `_command_json` → None → `stopped` jest False / reason nie `delivery_survey_unavailable`. CLOSED nadal stop.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
