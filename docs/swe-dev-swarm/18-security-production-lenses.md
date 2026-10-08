# Security and Production lenses

Child of #1551. Analysis only. No runtime change.

## What exists

src/lokay/proc/validate_pr_review.py allows eight finding categories. bug, security, performance, maintainability, test, style, documentation, and other. An unknown category fails closed.

A finding whose category is security sets secrets on the decision. src/lokay/pr_review.py then refuses to treat that decision as a soft nit. should_label_needs_review is true when secrets is true. Auto-repair does not run for a secrets decision. The comment says product and security judgment stay fail-closed.

There is no Production category and no Production lens. performance is the closest category, and it does not set a separate flag. The review request is still one plugin call per configured model, not one call per named lens.

## Gap

SWE-Dev wants a Security reviewer and a Production reviewer. Each has inputs, a veto, and a grade. Lokay folds a security finding into the secrets boolean. It has no production veto. A performance finding is just another finding in the same list.

The input to every lens is the same PR evidence. Nothing tells one call to look only at security and another only at production.

## What not to pretend

The secrets flag is not a Security lens. It is a consequence of one category inside a shared review. Adding the word production to the category set would not create the reviewer or its veto.

## Smallest later change

Pass a lens name on the review request. Keep the existing security category and the secrets stop. Add a production flag only when a named lens returns it. Do not add the lens in this note.
