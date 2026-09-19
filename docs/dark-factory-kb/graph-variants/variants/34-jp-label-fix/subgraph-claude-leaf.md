# Subgraph: claude-leaf

**Theme:** Claude Code CLI headless (`claude -p …`) jako **liść AGENT** — fix + opc. self-review; nie orkiestrator FSM.  
**Mode mix:** AGENT w CLI; test/lint gate + retry cap = DET.

## Flow

```mermaid
flowchart TD
  A([enter: cell ready]) --> B["AGENT: claude -p … --dangerously-skip-permissions"]
  B --> C{scope clear?}
  C -->|underspec / dangerous| D[DET: ask-or-stop comment]
  D --> Z0([leave: *-failed — no limbo])
  C -->|ok| E[AGENT SO: code changes in worktree]
  E --> F[DET: lint / test gate]
  F -->|fail + budget>0| G[DET: decrement retry]
  G --> B
  F -->|fail + budget=0| H[DET: evidence comment]
  H --> Z1([leave: *-failed])
  F -->|green Solvio lint / JBS tests| I[DET: commit on branch]
  I --> J[DET: push branch]
  J --> K([leave: branch ready → pr-ceiling])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  class D,F,G,H,I,J det
  class B,E agent
  class Z0,Z1 bad
```

## Retry budget (compose)

| Family | Gate | Cap | On exhaust |
|--------|------|-----|------------|
| Solvio | `pnpm check:fix` (lint) | timeout ~30m / single pass+ | `auto-fix-failed` |
| JBS | test loop | ≤3 tests + re-fix ≤2 | `agentic-fix-failed` + comment |
| KLEPACZ alias | project test cmd | N from env | `*-failed` |

## Notes

- **Reuse fidelity.** Headless Claude Code CLI na runnerze — ten sam wzorzec co w karcie `jp-label-auto-fix`, nie Marketplace monolith jako router.
- **Liść, nie orkiestrator.** Claude nie flipuje `in-progress`/`done`, nie zmienia MergePolicy, nie otwiera kolejnych issues. Wynik = diff + branch / fail.
- **Ask-or-stop.** Auth, billing, migracje, deps poza Allowed → comment + `*-failed` (KLEPACZ), nie „ulepsz po drodze”.
- **Meat ≡ AI.** To samo siedzenie: CLI albo człowiek-klepacz w worktree contract — graf bez zmian.
- **Flags.** `--dangerously-skip-permissions` tylko w izolowanej komórce worktree/runner; budżet turns/tools = DET wokół liścia.
- **Handoff contract.** `{branch, shas[], summary, retries_used}` \| `{skip, reason}` → pr-ceiling / failed.
