# CI and the human merge gate

Child of #1551. Analysis only. No runtime change.

## What exists

src/lokay/config.py defaults merge_enabled to false and require_checks to false. The comment says require_checks is local trust only and does not gate merges on CI unless turned on.

src/lokay/merge_policy.py decide_auto_merge returns disabled while merge_enabled is false. When the flag is true, a PR labeled ai:needs-review stays blocked. Checks must pass only when require_checks is true. A completed review must be approve with merge_ok. The function's own line says it decides whether an AI PR may auto-merge.

docs/WORKING.md states the live policy. With merge enabled, lokay merges in the same pr_triage pass when checks are green and the review is approve.

## Gap

SWE-Dev merge is human-only after seven passing reviews and green CI. Lokay can merge the product PR itself once merge.enabled is on. CI is optional unless require_checks is set. There is no separate merge-ready state that waits for a person.

Turning merge off makes the PR wait. That is a flag, not a named human gate with a recorded click.

## What not to pretend

This note does not flip the live config. The epic says product merges stay a human decision, and that change belongs to a later implementation ticket. Disabling merge here would also stop the current factory's Definition of Done, which is merged code on main.

## Smallest later change

Add an explicit merge-ready receipt that stops before gh pr merge, and require a human actor on the merge commit. Keep require_checks as the CI half. Do not silently disable the current auto-merge in this analysis.
