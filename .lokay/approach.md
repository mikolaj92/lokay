# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=303 -->

Repository: `mikolaj92/lokay`  
Issue: #303 — reap_stale_implementing: GraphQL 429 — skip repo, nie survey_error

## Goal

`gh issue list` GraphQL exhausted na jednym repo z katalogu. `reap_stale_implementing` / `gh_issues` pada adapter_failed. last-pass `health=survey_error`, LaunchAgent exit 1.

## Files likely touched

- `src/lokay/proc/reap_stale_implementing.py`
- `src/lokay/gh_issues.py`
- `tests/test_reap_stale_implementing.py`

## Test plan

- Sztuczny GraphQL 429 na jednym repo → skip, health nie survey_error.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
