# Lokay agent notes

## Design law

**Unix small programs + Fala graph for order.** See `docs/UNIX.md` and `docs/GRAPH.md`.

- New capability → new file under `src/lokay/proc/` + `project.scripts` entry.
- New ordering / branching → edit `fala/lokay.fala-package.toml` (conduction), not the agent.
- Do **not** grow `compose/*` with GitHub/git/Grok logic; call `graph_run` / atomics.
- Prefer ~50–100 line process modules.
- JSON on stdout (`envelope.ok` / `envelope.err`).
- Fala organ: `lokay.fala_organ` only maps atom name + conduction → atom CLI.

## Stack

- Agent: **Grok** (`lokay-run-grok`), not omp.
- No Hermes plugin, no Kanban, no Fala graph required.

## Verify

```bash
uv run pytest -q
uv run lokay-make-branch --repo a/b --issue 1 --title t
uv run lokay tick --config config.yaml
```
