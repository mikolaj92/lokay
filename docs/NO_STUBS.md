# No stubs / no silent inventing

Lokay is a **production lokay**. The following are **forbidden** in production
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
  agent: pi        # log label only
  command: pi      # binary on PATH
  args: [ ... ]    # argv template; omit model unless the harness needs it
```

The goal passed to the harness is always the same: implement the issue (or repair the PR) in the worktree; the orchestrator opens/merges the PR. Switching harness is a **config change**, not a code fork.

### Collector execution boundary

A separate intake gate may classify a seed as unbounded collection work. That
classification does not turn Pi into a collector: the harness may implement
only a bounded collector/bootstrap patch. The destination deployment starts the
collector durably in the background after merge; Pi and the lokay must not fill
its data store, poll progress, or wait for completion. A later issue evaluates
whether collection is accruing.

## Fail closed

- Empty `executor.agent` / `LOKAY_AGENT` → error (no silent default).
- Omitting `executor.agent` / `command` / `args` while `executor.enabled` is true → error (no silent Pi invent).
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
