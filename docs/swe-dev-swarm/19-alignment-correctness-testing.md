# Alignment, Correctness, and Testing

Child of #1551. Analysis only. No runtime change.

## What exists

src/lokay/pr_review.py stores scope_ok and tests_adequate on one decision. Both default to true. If either is false, the decision is not a soft nit and it does not approve.

Findings use categories. bug, test, and the others listed in validate_pr_review. A bug finding is a correctness note inside the shared list. A test finding is a testing note in that same list. Neither category starts its own review call.

Architecture is not a category. Codex is not a role. A second model in pr_review_models is another copy of the same request, folded into the same verdict.

## Gap

SWE-Dev wants an Alignment lens, a Correctness lens, and a Testing lens. Architecture and a second model are separate reviewers too. Each can veto.

Lokay has two booleans and two categories. scope_ok is the closest thing to alignment, and it is one bit on the shared decision. tests_adequate is the closest thing to the testing lens, and it is also one bit. There is no per-lens grade.

## What not to pretend

A false scope_ok is not an Alignment review. A bug finding is not a Correctness reviewer. A test finding is not a Testing reviewer. Another model string is not Codex.

## Smallest later change

When review requests gain a lens name, map scope_ok to alignment and tests_adequate to testing. Keep bug findings as correctness input. Add architecture only as a new named lens. Do not split the calls in this note.
