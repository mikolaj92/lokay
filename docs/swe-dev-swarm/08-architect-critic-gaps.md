# Architect and Critic gaps

Child of #1551. Analysis only. No runtime change.

## What exists

src/lokay/proc/build_issue_approach.py calls build_approach once. The inputs are the issue, the worktree, and one agent verdict.

src/lokay/approach_plan.py says the plan comes from that verdict. The fields are goal, files, test_plan, and non_goals. Issue prose is not parsed. There is no score field and no round field. render_approach_md writes .lokay/approach.md.

src/lokay/proc/validate_plan.py rejects a plan with no files. The reason is plan_incomplete. That checks shape. It does not call a second agent, and it does not return a grade.

## Gap

SWE-Dev Design is a loop. An Architect writes a design. A Critic scores it. They repeat until the score passes, and they stop at five rounds.

Lokay writes one approach file from one verdict. A bad shape stops the slot. A weak design that still names a file continues into coding. Nobody plays Critic, so there is no round to cap at five.

## What not to pretend

The coding executor is not an Architect, and validate_plan is not a Critic. Running the same executor again would be a retry, not a scored design loop.

## Smallest later change

Keep approach.md. Add a critic JSON next to it with an integer score and a round count. Stop at round 5. Do not start the coding executor until the critic score passes, and do not add that gate in this note.
