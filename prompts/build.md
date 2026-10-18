Only edit files inside the current working directory. Never edit ~/.lokay or any other checkout.
Search only inside the current working directory; never scan the home directory.
Implement the plan.
Never disguise text (encoding, escaping, splitting) to avoid a search or check match; permalinks to a specific commit stay unchanged.
Docs describe only how the project works. On every change read the docs you touch, delete what is stale or duplicated, and keep added doc lines <= removed doc lines.
No new unit test functions; change production code. Update existing tests only if the change invalidates them; in every existing test file added non-blank lines must not exceed removed non-blank lines (blank lines do not count), and never add test files. Never read or write GitHub tokens.
If you think the work is blocked, implement the smallest concrete part of the plan you can in this repo; only make zero changes if nothing at all can be done, and say why.
