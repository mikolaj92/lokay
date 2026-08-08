# No stubs / no silent inventing

Lokay is a **production mill**. The following are **forbidden** in production
code paths (and rejected by tests):

| Pattern | Why |
|---------|-----|
| `fake` / `stub` / `mock` / `noop` agent labels | Pretend work |
| Silent agent inventing (empty → default name) | Hides misconfig |
| `execute=True` while `executor.enabled=false` treated as success | Silent no-op |
| Plan-as-success when live execute was requested | Lies about work done |

## Real harness slot

There is **one** nondeterministic coding atom:

- CLI: `lokay-run-agent`
- Python: `lokay.agent.run_agent` / `lokay.proc.run_agent`

Harness identity is **not** baked into callers. Config owns the binary:

```yaml
executor:
  enabled: true
  agent: omp       # log label only
  command: omp     # binary on PATH
  args: [ ... ]    # argv template; omit model unless the harness needs it
```

The goal passed to the harness is always the same: implement the issue (or repair the PR) in the worktree; the orchestrator opens/merges the PR. Switching harness is a **config change**, not a code fork.

## Fail closed

- Empty `executor.agent` / `LOKAY_AGENT` → error (no silent default).
- `LOKAY_AGENT=fake|stub|mock|noop` → error.
- Empty `executor.command` or `executor.args` → error.
- `lokay-run-agent --live` without live mode + executor enabled → `ok: false` / refused.
- `run_agent(execute=True)` with executor off → raise.

## Historical notes

| Old smell | Status |
|-----------|--------|
| `or "grok"` invent harness | **Deleted** — fail closed |
| `lokay.grok_agent` re-export | **Deleted** |
| `lokay-run-grok` | **Deleted** — use `lokay-run-agent` |

Broader compat inventory: [`FALLBACKS.md`](FALLBACKS.md)
