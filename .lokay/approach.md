# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=287 -->

Repository: `mikolaj92/lokay`  
Issue: #287 — survey_ready: listuj work:ready (state all), nie filtr z ai:ready

## Goal

`survey_ready` woła `list_issues` → `list_ready_issues` (etykieta `config.ready_label` = `ai:ready`), potem filtruje `work:ready`. CLOSED z samym `work:ready` nigdy nie wchodzi na listę, więc park z #283 nie jedzie.

## Files likely touched

- `src/lokay/proc/survey_ready.py`
- `src/lokay/gh_issues.py`

## Test plan

- Lista: CLOSED+work:ready (bez ai:ready) + OPEN+work:ready → CLOSED parkowany, OPEN zostaje. Inbox / inne etykiety dalej `--state open`.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
