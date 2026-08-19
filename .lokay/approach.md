# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=226 -->

Repository: `mikolaj92/lokay`  
Issue: #226 — survey_inbox: stuck blocked — nie wrzucaj do inbox

## Goal

`plan_pass` (#224) i `dispatch_triage` (#222) skipują `blocked` w stuck.json. `survey_inbox` nadal wrzuca te issue do `inbox_issues_by_repo` — inbox się pęcznieje, triage_budget się marnuje zanim plan je wyfiltruje.

## Files likely touched

- `src/lokay/proc/survey_inbox.py`
- `tests/test_survey_inbox.py`

## Test plan

- Nowy `tests/test_survey_inbox.py` (albo dopisek): listed issues ma blocked + zwykły; w working tylko zwykły.
- Nie ruszaj 180–192.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
