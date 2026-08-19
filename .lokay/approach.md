# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=222 -->

Repository: `mikolaj92/lokay`  
Issue: #222 — dispatch_triage: stuck blocked — skip, nie nakładaj ai:ready

## Goal

Po park/plan_only issue (np. 190–192) wraca `ai:ready` przez `issue_triage`. `dispatch_triage` odpala każdy `triage_targets` bez spojrzenia w `stuck.json`. Survey zdejmuje `work:ready`, intake z powrotem maluje `ai:ready`.

## Files likely touched

- `stuck.json`
- `src/lokay/proc/dispatch_triage.py`
- `tests/test_dispatch_triage.py`

## Test plan

- Nowy `tests/test_dispatch_triage.py` (albo dopisek w istniejącym, jeśli jest): target blocked w stuck.json nie woła `run_path`; target nie-blocked woła.
- Nie ruszaj 180–192 (nie re-label, nie dispatch).

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
