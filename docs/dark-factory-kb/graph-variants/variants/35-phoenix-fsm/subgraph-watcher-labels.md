# Subgraph: watcher-labels

**Theme:** lokalny **Watcher** (`phoenixgithub watch` / `run-issue`) + etykiety `ai:*` = stany FSM; Watcher owns stages.  
**Mode mix:** 100% DET. Zero AGENT w kręgosłupie.

## Flow

```mermaid
flowchart TD
  A([enter: label event / watch tick / run-issue]) --> B[DET: read issue labels + payload]
  B --> C{impulse ai:ready or ai:revise?}
  C -->|no| Z0([leave: ignore])
  C -->|yes| D{exactly one active ai:* stage?}
  D -->|conflict / extras| E[DET: normalize mutex]
  E --> F{recoverable?}
  F -->|no| Z1([leave: drop illegal + receipt])
  F -->|yes| G[DET: claim issue]
  D -->|one| G
  G --> H[DET: remove impulse + add ai:in-progress]
  H --> I[DET: ensure branch phoenix/issue-N]
  I --> J[DET: audit comment / local log]
  J --> K([leave: handoff planner-coder])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  class B,C,D,E,G,H,I,J det
  class Z0,Z1 bad
```

## Transition table (compose Phoenix)

| From | Event / predicate | To | Who flips |
|------|-------------------|----|-----------|
| *(human)* | label `ai:ready` | claim → `ai:in-progress` | Watcher |
| *(human / loop)* | label `ai:revise` | claim → `ai:in-progress` | Watcher |
| `ai:in-progress` | Planner→Coder→Tester OK | handoff PR → `ai:review` | Watcher |
| `ai:in-progress` | test/agent fail | `ai:failed` | Watcher |
| `ai:failed` | `AUTO_REVISE` budget left | `ai:revise` | Watcher |
| `ai:failed` | cap / HITL | stay failed + receipt | Watcher |
| `ai:review` | human merge | `ai:done` | człowiek (+ optional script) |
| `*` | illegal multi-stage | normalize or drop | Watcher |

## Notes

- **Reuse fidelity.** Phoenix README: impulse `ai:ready` / `ai:revise` → Watcher `ai:in-progress` → pipeline → `ai:review` / `ai:failed` → revise loop → human `ai:done`.
- **Watcher owns FSM.** Stan żyje na issue labels — nie w pamięci agenta, nie w czacie. Executor = lokalny daemon/CLI (GHA mirror opcjonalny, nie kanon).
- **Agent never routes.** Role zwracają enum wyniku (`ok`/`fail`/`defer`); Watcher mapuje na tabelę. Poza tabelą = `ai:failed` albo ignore.
- **Mutex.** Jedna aktywna stage-label `ai:*` naraz; extras strip przed claim.
- **Handoff contract.** `{stage: in_progress, issue_id, branch: phoenix/issue-N}` albo `{ignore|drop}`.
