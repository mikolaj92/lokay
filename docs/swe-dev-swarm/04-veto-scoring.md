# Veto and scoring

Child of #1551. Analysis only. No runtime change.

## What exists

A review ends as approve or request_changes. src/lokay/proc/validate_pr_review.py sets request_changes when the normalized finding list is non-empty. Otherwise the verdict is approve.

src/lokay/proc/run_pr_review_agent.py rejects the fold when any lens is incomplete or names a different SHA. That path is fail_closed. It is not a grade.

src/lokay/config.py has no review score, no 94, and no 98. A search of the review modules finds no grade field and no veto enum.

## Gap

SWE-Dev wants a score schema. A means 94 or above from each reviewer. A+ means 98 for runtime-agent code. Red is a veto. Incomplete JSON stays fail-closed.

Lokay already keeps incomplete output fail-closed. It has no numeric score, so it cannot express 94, 98, or a red veto as data. request_changes is a boolean fold of findings, not a score from one named reviewer.

## What not to pretend

Adding the numbers 94 and 98 to a comment would not create the schema. There is no reviewer identity to attach a score to, and no cargo field to store it.

## Smallest later change

Define one score object per named lens, with reviewer, integer score, and veto boolean. Keep today's fail-closed rule for incomplete JSON. Do not threshold merge until that object exists and a later issue wires it.
