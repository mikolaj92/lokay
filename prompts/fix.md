Only edit files inside the current working directory. Never edit ~/.lokay or any other checkout.
Each finding's 'uzasadnienie' or 'reason' explains the concrete problem; fix exactly that.
Findings provide 'plik', 'linia_od', 'linia_do', and 'zmiana'; use them to locate and fix the failure.
Docs describe only how the project works. On every change read the docs you touch, delete what is stale or duplicated, and keep added doc lines <= removed doc lines.
Fix listed file/line notes and failures required to pass local checks. No new unit test functions. Never read or write GitHub tokens.
Never disguise text (encoding, escaping, splitting) to avoid a search or check match; permalinks to a specific commit stay unchanged.
Run local checks in the worktree until they pass; necessary check fixes take precedence over scope/alignment notes and must not be reverted. Do not commit, publish changes, or verify the PR or remote checks; lokay handles those operations.
If you believe a listed finding is wrong or cannot be acted on, edit no files and end your reply with a section '## Dispute' containing, per finding, `<pytanie> <plik>:<linia_od>-<linia_do>: <why the finding is wrong or not actionable>`.
