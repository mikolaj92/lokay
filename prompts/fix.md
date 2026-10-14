Only edit files inside the current working directory. Never edit ~/.lokay or any other checkout.
Each finding's 'uzasadnienie' or 'reason' explains the concrete problem; fix exactly that.
Named checks provide 'name', 'location', and 'fix_hint'; use them to locate and fix the failure.
Hard rule: write no code comments at all (no comment lines, no docstrings), keep documentation to a minimum, and add no unit tests.
Fix only the listed file and line notes, and the failing tests. Do not add new unit test files or functions. Commit on this same branch.
Making CI green takes precedence over scope/alignment notes: changes needed for CI to pass are in scope and must not be reverted.
If you believe a listed finding is wrong or cannot be acted on, make no commit and end your reply with a section '## Dispute' containing, per finding, `<pytanie> <plik>:<linia_od>-<linia_do>: <why the finding is wrong or not actionable>`.
