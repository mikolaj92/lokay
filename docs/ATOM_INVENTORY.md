# Read-only atom inventory

Run from the repository root:

```sh
uv run lokay-atom-inventory
```

Use `--package PATH --source PATH` to inspect another authored manifest and
its matching `lokay` source directory. The command parses TOML and Python AST.
It does not import inspected code, invoke handlers, run adapters, retry effects,
or write product journals. Stdout is one JSON envelope.

`nodes` preserves each authored path/effector occurrence. `authored_kind`
distinguishes correlation paths from unexpanded path templates. `sites` lists
relative source files and one-based line numbers. A `candidate` is a comparison
or prefix site, not proven dispatch ownership. `direct_module` identifies an
existing module named by a subprocess command, not its transitive dependencies.
`unresolved` and `unresolved_template` remain explicit; template candidate sites
may be useful without proving any expanded binding.

`summary` counts authored nodes, distinct atom names, unique candidate sites and
unresolved nodes separately. None of these counts proves the number of distinct
implementations or whether an atom hides a workflow. Ripwire is not required and
is never dispatch authority.

Execution identity and historical failure inspection are separate follow-ups
(#1089 and #1091). Harvest migration is tracked in #1090. The inventory does not
claim those tasks are complete.
