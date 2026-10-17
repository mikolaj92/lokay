Only edit files inside the current working directory. Never edit ~/.lokay or any other checkout.
Each finding's 'uzasadnienie' or 'reason' explains the concrete problem; fix exactly that.
Named checks provide 'name', 'location', and 'fix_hint'; use them to locate and fix the failure.
Hard rule: write no code comments at all (no comment lines, no docstrings), keep documentation to a minimum, and add no unit tests.
Fix only the listed file and line notes, and the failing tests. Do not add new unit test files or functions. Edit files only; lokay commits and pushes.
Local checks in the worktree must pass. Making local checks pass takes precedence over scope/alignment notes: changes needed to make local checks pass are in scope and must not be reverted.
If you believe a listed finding is wrong or cannot be acted on, edit no files and end your reply with a section '## Dispute' containing, per finding, `<pytanie> <plik>:<linia_od>-<linia_do>: <why the finding is wrong or not actionable>`.
