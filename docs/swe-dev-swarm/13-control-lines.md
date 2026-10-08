# Control lines

Child of #1551. Analysis only. No runtime change.

## What exists

Fala owns the order. README names the departments in one pass. Triage does not code. The executor starts one issue_to_pr. PR triage reviews and may merge. PR repair runs only after a repair verdict.

The pass receipt is the observable handoff. README says root_reason keeps the child failure apart from the parent reason. trace carries the db, run_id, and path_id to the Fala journal. A started worker is occupancy. A published PR or a merge is delivery.

src/lokay/activity.py reset_activity marks the start of a daemon entry. It is a heartbeat of the current atom, not a stage owner.

src/lokay/compose/human_mailbox.py lists residual ai:needs-review items. That is a mailbox, not a control token passed from Review to a person.

## Gap

SWE-Dev wants a named handoff at Design, Build, Review, and Merge. Each line says who held control and who received it. A human holds control only at merge, and when the loop is stuck.

Lokay records atoms and receipts. It does not record a from-role and a to-role. Merge control is the merge.enabled flag inside pr_triage, not a human receipt.

## What not to pretend

A Fala path_id is not a control line. The journal can show which atom ran. It cannot show that an Architect handed a design to an Implementer, because those roles are not in the graph.

## Smallest later change

Add one handoff record per stage change. Store from, to, artifact digest, and time. Point it at the existing trace path_id. Do not invent the missing roles in that record.
