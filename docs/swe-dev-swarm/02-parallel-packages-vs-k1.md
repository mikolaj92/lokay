# Parallel packages versus one worktree

Child of #1551. Analysis only. No runtime change.

## What exists

Build is one worktree and one open AI PR per repository.

docs/WORKING.md says the executor budget is limits.max_issue_to_pr_per_pass, default 1. That budget is a pass budget, not concurrent worktrees. At most one attempt and one open AI PR per repo. K greater than 1 is rare breadth across already-isolated clean repos, not concurrent workers in one repo.

src/lokay/config.py sets max_issue_to_pr_per_pass to 1.

The delivery sequence is one worktree from origin/main, one plan, one executor, one rebase, one test run, one push, and one PR.

## Where parallelism already exists

src/lokay/proc/run_pr_review_agent.py runs one request per review lens, all on the same SHA. review_requests builds that list from pr_review_model plus pr_review_models. collapse folds every lens into one verdict. Any incomplete lens fails the review.

That parallelism is review-only. It does not split the patch into packages, and it does not give each package an implementer and a tester.

## Gap

SWE-Dev Build wants a design split into packages, each with an implementer, a tester, and a package critic, running at the same time, then one integrate step. Lokay has no package cargo, no per-package worktree, and no integrate stitch. The occupancy law forbids a second open AI PR in the same repo.

## What not to pretend

Several review models are not several build packages. Raising K does not create package isolation. It only allows another repo in a later slot.

## Smallest later change

Keep K=1. Define a package list inside the one worktree and run package tests in that same tree before the PR. A second worktree per package is a later isolation issue, not this note.
