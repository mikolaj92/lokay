# Graph and triage versus a Design phase

Child of #1551. Analysis only. No runtime change.

## What exists

Lokay has no Architect and no Critic. A ready issue goes from triage to one coding slot.

docs/WORKING.md names the executor path. One issue becomes one open PR. The budget is limits.max_issue_to_pr_per_pass, default 1. The sequence inside that slot is a worktree from origin/main, then plan_issue, then the configured executor, then commit, rebase, tests, push, and a PR.

src/lokay/config.py sets max_issue_to_pr_per_pass to 1. README states the same serial issue_to_pr law.

src/lokay/approach_plan.py builds the plan from one executor JSON verdict. The fields are goal, files, test_plan, and non_goals. It does not score that verdict, and it does not loop. src/lokay/proc/validate_plan.py rejects a plan with no files. That is a shape check, not a design score.

src/lokay/triage.py classifies an issue as ready, skip, split, out_of_scope, or blocked. Split cuts an oversized issue. It does not write a design and it does not run a critic for five rounds.

## Gap

SWE-Dev Design wants an architect draft, a critic score, and up to five rounds before build. Lokay has none of those roles, no design score, and no round counter. The first coding executor both plans and writes the patch.

Triage can split an issue into children. That is the closest current cut, and it happens before any design document exists.

## What not to pretend

A green plan_issue is not a passed design. K=1 is still the factory law. Parallel packages belong to #1553, not this note.

## Smallest later change

Add a design document and a numeric critic result as cargo for one issue, still inside the single worktree, before the coding executor starts. Keep K=1 until the migration issue says otherwise.
