# Migration from K=1

Child of #1551. Analysis only. No runtime change.

## What stays

README and docs/WORKING.md keep implementation serial. limits.max_issue_to_pr_per_pass defaults to 1. One open AI PR per repo. One worktree per branch. Each Fala node returns one JSON envelope. Incomplete review fails closed. A started worker is not delivery.

Those rules stay until a later ticket changes one of them. This note does not raise K and does not turn merge off.

## Order

1. Cargo. Add one versioned JSON beside .lokay/approach.md with paths for design, packages, findings, and scores. Leave the hashed review artifact where persist_result writes it.

2. Design, still in the one worktree. Add a critic result with a score and a round count next to the approach file. Stop at five rounds. Do not start the coding executor until that score passes.

3. Named review lenses, still one SHA. Pass a lens name into the existing review request. Map scope_ok, tests_adequate, and the security category onto those names. Add grades only after the lens name exists. Keep the repair cap at 2 until a ticket chooses 10.

4. Packages inside the same ticket branch. A package list in cargo. Run the declared test command once per package and store the exit status. No second worktree yet.

5. Isolation. One branch and one worktree_dir per package. One writer per directory. Integrate by merging those branches back into the ticket branch. Only then consider more than one worker, and only under separate package ids. The repo occupancy lock stays.

6. Human merge. A merge-ready receipt that stops before gh pr merge. require_checks stays the CI half. Do this last, in its own ticket, because today's Definition of Done is a merged main.

## What this order refuses

Parallel packages before cargo and worktree isolation. Grades before named lenses. A human-only merge switch hidden inside an analysis PR. Copying the numbers 5, 10, 94, and 98 into config before the fields exist.

## Done for the epic

The swarm notes name the gaps. Implementation stays on new tickets. A person merges those tickets.
