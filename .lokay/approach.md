# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=184 -->

Repository: `mikolaj92/lokay`  
Issue: #184 — Real diff + pi over budget: commit/pr bez czekania na exit

## Goal

Influenzer#137 i #177: pi napisał kod, spał 8–10 min, `issue_to_pr` nie zrobił PR. Olej musiał odpalić `commit_all`+`push_branch`+`pr_create`. lokay#180 (to samo) padło plan_only — **nie wracać do #180**.

## Files likely touched

- `lokay/approach.md`
- `localize.json`

## Test plan

- Real plik + over_budget → committed/pr attempted. Tylko `.lokay/*` → nie commit.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
