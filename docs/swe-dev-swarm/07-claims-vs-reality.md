# SWE-Dev claims versus Lokay

Child of #1551. Analysis only. No runtime change. The local workflow.html brief is not in this checkout, so the claims below are the ones named on the epic.

## Claim and the code

The epic says Design is an Architect plus a Critic for up to five rounds. README and docs/WORKING.md describe five departments and a serial issue_to_pr. Triage does not start coding. The executor department dispatches one child. No Architect atom and no Critic atom are named.

The epic says Build runs packages in parallel, each with an implementer, a tester, and a package critic. README says implementation is serial, default K=1, and expansion keeps that serial graph. One department slot is one ticket.

The epic says Review is seven named reviewers, grades 94 and 98, and a red veto. The review path collapses configured models to approve or request_changes. Incomplete JSON fails closed. There is no grade.

The epic says a human merges. docs/WORKING.md says that with merge enabled, lokay merges in the same pr_triage pass when checks are green and the review approves. merge_enabled defaults to false, so auto-merge is a switch, not an absent path.

The epic says a stuck loop goes to a human. stuck.json counts delivery misses. It does not count design rounds or review-fix rounds. ai:needs-feedback is documented as a rare residual, not the default stop.

## What is already true

Fail-closed review is real. An incomplete lens is not a review. A started worker is not delivery. Done is merged code on main. Those rules should stay while the missing roles are designed.

## What not to pretend

Serial K=1 is not a quiet version of parallel packages. One approve is not seven grades. A factory merge is not a human merge.
