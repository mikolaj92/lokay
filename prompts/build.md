Only edit source files inside the current working directory. Never edit another checkout or Lokay state.
Use $VALIDATION_DIR for validation artifacts; never create .validation in the worktree. Cache environment paths are writable.
Search only inside the current working directory; never scan the home directory.
Implement the plan. Commit the production code on this branch.
Hard rule: write no code comments at all (no comment lines, no docstrings), keep documentation to a minimum, and add no unit tests.
Do not add new unit test files or new test functions; change production code. Only update an existing test if the change makes it wrong. Do not read or write GitHub tokens.
If you think the work is blocked, implement the smallest concrete part of the plan you can in this repo and commit it; only make zero changes if nothing at all can be done, and say why.
