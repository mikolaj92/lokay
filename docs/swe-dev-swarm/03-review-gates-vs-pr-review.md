# Review gates versus one collapsed verdict

Child of #1551. Analysis only. No runtime change.

## What exists

src/lokay/config.py stores one pr_review_model and an optional pr_review_models tuple. There is no score field and no threshold of 94 or 98.

src/lokay/proc/run_pr_review_agent.py builds one request per configured model, all for the same SHA. The primary model is first. collapse requires every lens to return approve or request_changes for that SHA. Any incomplete lens fails the whole review.

The folded verdict is request_changes when any lens says so or when any finding exists. Otherwise it is approve. Findings are concatenated. A lens cannot veto by name, and a low score cannot exist because no score is read.

## Gap

SWE-Dev Review wants seven named reviewers. Alignment, Architecture, Security, Production, Testing, Correctness, and a second model. Each may veto. A grade below 94 fails, and runtime-agent code wants 98. Lokay has an unnamed model list, two verdict words, and no grade.

A second model is a lens. It is not a named reviewer with its own veto record.

## What not to pretend

Fail-closed on an incomplete lens is not a veto score. Approve is not an A. The product law still merges from a completed approve, not from seven passing grades.

## Smallest later change

Name the lenses in the collapsed JSON and keep the current fail-closed rule. Add numeric grades only in a later threshold issue. Do not invent 94 inside this note.
