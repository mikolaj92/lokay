# Cargo and artifacts

Child of #1551. Analysis only. No runtime change.

## What exists

The plan is a markdown file in the worktree. src/lokay/approach_plan.py writes .lokay/approach.md. It holds the goal, likely files, test plan, and non-goals from one verdict.

The code is the git branch. There is one worktree and one PR. Findings travel in the review comment and in the decision JSON.

src/lokay/proc/pr_review_artifacts.py persist_result writes one immutable JSON file. The directory is pr_review_artifacts_dir/results/repo/pr. The file name is the head SHA, a dash, and the sha256 of the body. A different body for the same name is an artifact conflict. The loader refuses a file whose bytes do not match the digest.

That JSON is a review result. It is not a design, not a package plan, and not a score.

## Gap

SWE-Dev cargo is one schema with five parts. Design, package plans, code, findings, and scores. Each part has a path and a handoff to the next role.

Lokay has two durable pieces and a branch. The approach file is not hashed into the review artifact. Scores do not exist. Package plans do not exist. Nothing names which role may write which file.

## What not to pretend

The review artifact is durable and fail-closed. That does not make it the cargo schema. Folding the approach markdown into that JSON without a version would mix a plan with a verdict.

## Smallest later change

Add one cargo JSON beside the approach file. Give it a schema version and paths for design, packages, findings, and scores. Leave the review artifact where it is until a later ticket points cargo at its digest.
