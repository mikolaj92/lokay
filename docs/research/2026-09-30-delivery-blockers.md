# Lokay delivery audit — 2026-09-30

## Intended behavior (history, newest law first)

- 2026-09-28 history: one resident Lokay, no service pass/time ceiling; Fala owns work order. Issue #1396 tracks resident lifecycle. A failed tick must not end the service.
- 2026-09-22 operator instruction: real merge on main is the measure; one live operator, no second executor; per-repo PR before new issue; one named blocker -> one factory fix; no forced merge, bypassed tests, or new HITL gates.
- Current Scope C (#1404): empty scope means every enabled catalog repo. Only ai:ready / ready-for-agent starts implementation; executor reuses intake list.
- WORKING.md: quality code reviewed, tested and merged is DoD. Agent ok, open PR, hosted/progress receipt is not delivery.

## Actual code and first failed boundary

LaunchAgent -> scripts/lokay-service.sh -> daemon.main -> lock/preflight -> daemon_entry -> daemon_cycle -> recovery_factory -> factory_pass -> harvest -> host_ff -> host gate -> begin -> issue_triage -> executor -> pr_triage -> pr_repair -> receipt.

1. Original host root was the dirty developer checkout at 6a494497. Eight commits behind c817d4da. host_ff refused dirty checkout. None of the newly merged fixes could run. Owner local edits include review upgrade and unfinished #1396; they were not discarded.
2. Shell from main still passes max-passes=8 and a 2400s watchdog; daemon calls one bounded entry graph and exits. Plist KeepAlive=true is already resident intent, but restarting a bounded process is not one resident Fala lifecycle. Issue #1396 remains open; do not implement a second Python scheduler as a shortcut.
3. Shell had no TERM/INT trap. bootout left its isolated daemon alive. New real-shell regression reproduced the orphan; shutdown now stops cycle tree and waits, retaining registered detached workers per existing stop_cycle_tree policy.
4. Host review config pinned OCR v1.12.10 while main pins v1.12.7. A canonical manifest included a different plugin executable identity. Preflight hid causes behind invalid/untrusted_review_config.
5. Preflight verified review file hashes but not tool-registry semantics. Trusted local tools had four tools; main plugin requires six. Preflight green, then product review failed tools_allowlist_invalid. New preflight uses the plugin validator, failing before GitHub feedback pollution.

## Host remediation (outside repository policy)

- Clean independent clone ~/.lokay/host at c817d4da; uv sync --extra dev.
- Local config/catalog under ~/.lokay/host-config; Lokay catalog clone points to runtime clone. Same state/worktree locations, full catalog, no scope clamp.
- Plist backup under ~/.lokay/backups; program/root/config switched to runtime clone.
- Runtime config uses existing pinned OCR v1.12.7, verified binary hash, runtime plugin absolute path and its own canonical manifest. Owner v1.12.10 files remain untouched.
- Runtime tools copied from main plugin's six-tool registry; validated and manifest regenerated. No bypass of review or tests.

## Live evidence after deployment

factory-pass-70700-61f4ee47f3f9:
- harvest, host_ff, host gate, begin, issue_triage, executor and PR triage all executed.
- ShowMeThePlayer #17 worker detected existing PR #34 and skipped new delivery; no duplicate PR.
- PR triage splot #57 failed tools_allowlist_invalid; tools repaired for following runs.
- 10:47:53Z receipt: health=hosted, progress=1, outcome=none, merged_count=0. Not working by DoD.
- Subsequent run passes the host boundary and reaches PR triage; vendor review currently fails ocr_invocation_failed. That remains a distinct unresolved transport/sandbox boundary, not a product request_changes verdict.

## Remaining named work

- #1396: resident Fala lifecycle, bounded child work, graceful termination/backoff, no service-wide kill timer.
- OCR invocation transport/sandbox evidence: identify exact failed subprocess before changing gates. Never replace the reviewed engine with direct Pi to make tests green.
- Infrastructure review failure must not become permanent product escalation; verify fail_closed recovery and same-SHA retry after host config repair.
- Product receipt reports hosted/progress on feedback without merge. Preserve counters but never claim delivery from those.
- Reconcile owner review-upgrade and daemon edits separately; no bulk commit of unknown local changes.

## Fixes in this change

- Config preflight reports validation fields; review preflight reports safe typed failure code.
- Review preflight validates tool registry through the existing plugin library.
- TERM/INT caretaker cleanup stops its cycle tree and waits.

No delivery claim until an actual reviewed, tested merge is observed.
