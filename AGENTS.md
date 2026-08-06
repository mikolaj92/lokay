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

- Agent: **Grok** / `fake` via `lokay-run-agent` (harness is swappable).
- Process order: **Fala** (`fala/lokay.fala-package.toml`).
- No Hermes plugin, no Kanban ledger for step order.

## Tooling law

**Always `uv`, never bare `python3` / `python`.**

```bash
uv run pytest -q
uv run lokay …
uv run python -m lokay.fala_organ   # only if needed; prefer entrypoints
```

Fala organs are invoked as:

`uv run --project <lokay-root> python -m lokay.fala_organ`

## Verify

```bash
uv run pytest -q
uv run lokay-make-branch --repo a/b --issue 1 --title t
uv run lokay path --describe
uv run lokay status --config config.yaml
uv run lokay tick --config config.yaml
```
