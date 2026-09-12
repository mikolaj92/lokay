# Subgraph: label-fsm

**Theme:** etykiety = stany FSM; **label FSM owns stages** — tylko GHA/skrypt flipuje; mutex jednej aktywnej stage-label.  
**Mode mix:** 100% DET. Zero AGENT w kręgosłupie.

## Flow

```mermaid
flowchart TD
  A([enter: issues.labeled / dispatch]) --> B[DET: read issue labels + event]
  B --> C{start label allowlisted?}
  C -->|no auto-fix / agentic-fix / ready-for-agent| Z0([leave: ignore])
  C -->|yes| D{exactly one active stage?}
  D -->|conflict / extras| E[DET: normalize mutex]
  E --> F{recoverable?}
  F -->|no| Z1([leave: drop illegal + receipt])
  F -->|yes| G[DET: lookup JP transition table]
  D -->|one| G
  G --> H{event legal for stage?}
  H -->|no| Z2([leave: ignore + receipt])
  H -->|yes start| I([leave: handoff gha-dispatch])
  H -->|yes advance next| J[DET: remove old + add next stage]
  J --> K[DET: audit comment / check-run]
  K --> Z3([leave: advanced])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  class B,C,D,E,G,H,J,K det
  class Z0,Z1,Z2 bad
```

## Transition table (compose JP)

| From | Event / predicate | To | Who flips |
|------|-------------------|----|-----------|
| *(human)* | label `auto-fix` (Solvio) | start → GHA | człowiek |
| *(human)* | label `agentic-fix` (JBS) | start → GHA | człowiek |
| `auto-fix` / `agentic-fix` | job accepted | `in-progress` | GHA |
| `in-progress` | PR created + green | `*-done` | GHA |
| `in-progress` | cap / ask-or-stop / install fail | `*-failed` | GHA |
| `*-done` | human merge | terminal stay | człowiek |
| `*-failed` | human re-label start | re-drive | człowiek |
| `*` | illegal multi-stage | normalize or drop | GHA |

## Notes

- **Reuse fidelity.** Solvio: `auto-fix` → `in-progress` → `done`/`failed`. JBS: `agentic-fix` / `agentic-fix-failed` (+ done). Alias `ready-for-agent` mapuje na ten sam start seat (KLEPACZ).
- **FSM owns stages.** Stan żyje na issue labels — nie w pamięci agenta, nie w czacie. To samo DNA co `09-label-fsm`, słownik krótszy (bugfix DIY).
- **Agent never routes.** Nawet gdy Claude „sugeruje” kolejną etykietę — skrypt czyta enum wyniku (`ok`/`fail`/`defer`) i **sam** mapuje na tabelę. Poza tabelą = `*-failed` albo ignore.
- **Mutex.** Jedna aktywna stage-label naraz; extras strip przed dispatch.
- **Handoff contract.** `{stage, issue_id, family: solvio|jbs|klepacz, next?}` albo `{ignore|drop}`.
