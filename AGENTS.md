# Lokay agent notes

## Design law

**Unix small programs.** See `docs/UNIX.md`.

- New capability → new file under `src/lokay/proc/` + `project.scripts` entry.
- Do **not** grow `compose/*` with GitHub/git/Grok logic; call atomics.
- Prefer ~50–100 line process modules.
- JSON on stdout (`envelope.ok` / `envelope.err`).

## Stack

- Agent: **Grok** (`lokay-run-grok`), not omp.
- No Hermes plugin, no Kanban, no Fala graph required.

## Verify

```bash
uv run pytest -q
uv run lokay-make-branch --repo a/b --issue 1 --title t
uv run lokay tick --config config.yaml
```
