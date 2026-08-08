# No stubs (binding)

Lokay is a **production mill**. The following are **forbidden** in production
config, LaunchAgent env, and runtime agent selection:

| Forbidden | Why |
| --- | --- |
| `agent: fake` / `stub` / `mock` / `noop` | Do not pretend to fix issues |
| Canary-only agents that write marker files | Not real work |
| Green ticks that claim progress without agent/gh/git mutations | Lies about WORKING |
| Shipping `LOKAY_CANARY.md`-style artifacts as “fixes” | Noise |
| Silent agent/model inventing (`or "grok"`, empty → default harness) | Hides misconfig |
| `--live` agent run that returns planned/ok when executor off | Synthetic success |

## Required

- **Real coding harness only** — currently `executor.agent: grok` (invokes `grok` CLI).
- Config and env that claim `live` must actually enable executor + mill policy you intend.
- Unit tests may use local fakes (`_FakeRunner`) **only inside `tests/`** to mock `gh`/IO — never as the mill agent.

## Enforcement

- `lokay.agent.resolve_agent_kind` / `run_agent` raise on stub names **and** on empty agent.
- Empty `executor.agent` / `executor.command` fails at config load (no silent re-fill).
- `execute=True` with `executor.enabled=false` raises (no plan-as-success fallback).
- `lokay-run-agent --live` without live mode + executor enabled returns `ok: false` / `status: refused`.
- Model unset → omit `-m` (CLI default); never substitute another model string.
- `LOKAY_AGENT=fake|stub|mock|noop` raises at config load.
- Continuous mill LaunchAgent must set `LOKAY_AGENT=grok` (or another **real** harness when added).

## AI-path inventory (issue #18)

| Location | Former risk | Decision |
| --- | --- | --- |
| `resolve_agent_kind` `or "grok"` | Invent harness when empty | **Deleted** — fail closed |
| `load_config` `agent or "grok"` | Empty string → grok | **Deleted** — fail closed |
| `run_agent(execute=True)` + executor off | Silent planned | **Fail closed** (raise) |
| `lokay-run-agent --live` + blocked | ok + planned | **Fail closed** (err/refused) |
| Model missing | Invent model name | **None** — omit `-m` only |
| Reviewer backends / multi-LLM clients | N/A in this tree | No multi-backend code |

If you need a dry pass without mutations, use **`mode: dry-run`** or omit `--live`.
That is not a stub agent — it is an explicit non-mutating mode.
