Only edit files inside the current working directory. Never edit ~/.lokay or any other checkout.
Fix only the listed file and line notes, and the failing tests. Do not add new unit test files or functions. Commit on this same branch.
Making CI green takes precedence over scope/alignment notes: changes needed for CI to pass are in scope and must not be reverted.
