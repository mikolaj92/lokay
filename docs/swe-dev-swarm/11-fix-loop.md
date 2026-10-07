# The review fix loop

Child of #1551. Analysis only. No runtime change.

## What exists

src/lokay/config.py sets max_request_changes_per_pr to 2. The comment says the next step is escalation to ai:needs-review. Values below 1 are rejected.

docs/WORKING.md says request_changes may auto-repair a few times, then escalate. The count is published review markers whose verdict is request_changes, one per head SHA.

The repair sees the PR, the review comment, and the current worktree. It does not receive a cargo bundle of design, package plans, scores, and prior fix diffs. The next round is another factory pass on that PR, not a Fixer role with a private inbox.

Stop conditions today are a merged PR, a closed PR, the cap of 2, or a fail-closed review. Hitting the cap labels the PR ai:needs-review and stops auto repair.

## Gap

SWE-Dev Fix runs up to 10 rounds. Each round carries cargo. The Fixer sees findings and the last package state. Round 10 hands the PR to a human.

Lokay stops at 2 request_changes markers. The human handoff is the label, not round 10. There is no cargo object between rounds.

## What not to pretend

Raising the cap from 2 to 10 would not create the Fixer or the cargo. It would only allow more automatic repairs of the same kind.

## Smallest later change

Write a round file next to the review artifact. Store the round number, the findings digest, and the head SHA. Stop auto repair when that file reaches the configured cap. Keep today's default of 2 until a later ticket chooses 10.
