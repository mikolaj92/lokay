Only edit files inside the current working directory. Never edit ~/.lokay or any other checkout.
Each finding's 'uzasadnienie' or 'reason' explains the concrete problem; fix exactly that.
Findings provide 'plik', 'linia_od', 'linia_do', and 'zmiana'; use them to locate and fix the failure.
Docs describe only how the project works. On every change read the docs you touch, delete what is stale or duplicated, and keep added doc lines <= removed doc lines.
Fix only listed file/line notes and failing tests. No new unit test functions.
Never disguise text (encoding, escaping, splitting) to avoid a search or check match; permalinks to a specific commit stay unchanged.
Local checks in the worktree must pass. Making local checks pass takes precedence over scope/alignment notes: changes needed to make local checks pass are in scope and must not be reverted.
If you believe a listed finding is wrong or cannot be acted on, edit no files and end your reply with a section '## Dispute' containing, per finding, `<pytanie> <plik>:<linia_od>-<linia_do>: <why the finding is wrong or not actionable>`.
