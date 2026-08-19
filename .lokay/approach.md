# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=285 -->

Repository: `mikolaj92/lokay`  
Issue: #285 — list_ready: work:ready ze state all, nie tylko OPEN

## Goal

`survey_ready` po #283 parkuje CLOSED, ale `list_ready_issues` / `list_issues_with_label` woła `gh issue list --state open`. CLOSED z leftover `work:ready` nigdy nie wchodzą na listę, więc park się nie odpala.

## Files likely touched

- `src/lokay/gh_issues.py`

## Test plan

- Lista ma OPEN+CLOSED z work:ready → CLOSED nie ląduje w remaining_ready (park). OPEN zostaje.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
