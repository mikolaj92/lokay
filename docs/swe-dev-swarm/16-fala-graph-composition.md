# Fala graph composition for new stages

Child of #1551. Analysis only. No runtime change.

## What exists

Order is the product. README says one tick runs daemon_cycle, which chooses recovery or one factory_pass. The factory starts with host_ff, then the host gate, then factory_begin on the begin route.

The parent then runs five departments in authored order. Self-repair, issue triage, the executor, PR triage, and PR repair. Each is a switch plus a child Fala. record_pass writes the receipt. factory_pass_terminal ends the pass.

docs/GRAPH.md says every node is a separate Unix process that returns one JSON envelope. Fala claims, asks, and records. It does not become the child. A node that does not return leaves the pass unfinished. There is no long-running program inside the graph.

New stages are not plugged in beside that list. The package in fala/lokay.fala-package.toml is the source. src/lokay/data/lokay.fala-package.toml is a byte copy. CI fails if they drift.

## Gap

SWE-Dev wants Design, Build, and Review as stages. Design would be an Architect and Critic loop. Build would be packages. Review would be seven lenses and a fix loop.

Those stages have no path id. Putting them inside the executor department would hide a loop inside one atom. A hanging daemon that waits for five critic rounds would break the one-envelope rule.

## What not to pretend

The five departments are not the three SWE-Dev stages under other names. Triage is not Design. The executor is not parallel Build. PR triage is not seven graded reviewers.

## Smallest later change

Add one correlation path per stage, each effector a Unix process with one JSON result and retry_policy none. Conduct the next stage only from a terminal envelope. Keep factory_pass as the parent that calls those paths. Do not add the paths in this note.
