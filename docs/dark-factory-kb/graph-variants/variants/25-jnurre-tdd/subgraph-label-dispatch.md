# Subgraph: label-dispatch

**Theme:** etykiety `agent*` = impuls + stan FSM; tylko GHA / sandbox-pal dispatch wolno flipować; mutex jednej aktywnej stage-label.  
**Mode mix:** 100% DET. Zero AGENT w kręgosłupie.

## Flow

```mermaid
flowchart TD
  A([enter: issues.labeled / PR review|merge]) --> B[DET: read labels + event payload]
  B --> C{known agent* label?}
  C -->|no| Z0([leave: ignore + receipt])
  C -->|yes| D{exactly one active stage?}
  D -->|0 or >1| E[DET: normalize / strip extras]
  E --> F{recoverable?}
  F -->|no| Z1([leave: drop illegal])
  F -->|yes| G[DET: lookup sandbox-pal transition table]
  D -->|one| G
  G --> H{event legal for stage?}
  H -->|no| Z2([leave: ignore + receipt])
  H -->|yes| I[DET: dispatch subgraph for stage]
  I --> J{subgraph returned advance?}
  J -->|no / hold| Z3([leave: stay + receipt])
  J -->|yes + next_label| K[DET: remove old stage + add next]
  K --> L[DET: audit comment / check-run]
  L --> Z4([leave: advanced])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  class B,E,G,I,K,L det
  class Z0,Z1,Z2 bad
```

## Transition table (jnurre native)

| From | Event / predicate | To | Who flips |
|------|-------------------|----|-----------|
| *(none)* | human labels `agent` | triage queue | człowiek |
| `agent` | job start | triage→plan slot | GHA |
| plan posted | wait HITL | stay until approve | — |
| plan | `agent:plan-approved` | `agent:implement` | GHA |
| plan | reject / timeout | `agent:needs-info` | GHA |
| `agent:implement` | TDD green + review handoff | review slot | GHA |
| `agent:implement` | SO fail / tests red @cap | `agent:needs-info` | GHA |
| review | approve | `agent:pr-open` | GHA |
| review | changes + budget>0 | `agent:revision` | GHA |
| review / revision | cap | `agent:review-unresolved` | GHA breaker |
| `agent:revision` | re-enter | `agent:implement` / TDD | GHA |
| `agent:pr-open` | changes requested | `agent:revision` | GHA on review |
| `agent:pr-open` | merged | cleanup → done | GHA |

## Notes

- **sandbox-pal impulse.** `issues: labeled` jest jedynym wejściem w kolejkę; review/merge eventy re-drive'ują revision/cleanup bez nowego mózgu.
- **Mutex.** Jedna aktywna stage-label naraz — normalize przed każdym flipem (duch chippingway `workflow:*` / 09-label-fsm).
- **Agent never routes.** SO może zwrócić enum `next`, ale **tylko** tabela mapuje go na etykietę. Poza tabelą = `agent:needs-info` / drop.
- **Concurrency.** Dispatch profiles + runner occupancy: K=1 per issue (fresh worktree); drugi impuls na to samo issue → defer/receipt.
- **Handoff:** `{stage, issue_id, event, next?}` albo `{drop|ignore}`.
