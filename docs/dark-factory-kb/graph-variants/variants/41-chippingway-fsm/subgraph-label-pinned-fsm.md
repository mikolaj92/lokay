# Subgraph: label-pinned-fsm

**Theme:** `workflow:*` = stan + **pinned JSON** = mirror; tylko lokalny orchestrator flipuje; mutex jednej stage-label.  
**Mode mix:** 100% DET. Zero AGENT w kręgosłupie.

## Flow

```mermaid
flowchart TD
  A([enter: poll tick / workflow label event]) --> B[DET: read labels + pinned JSON]
  B --> C{label and pin agree?}
  C -->|mismatch| D[DET: reconcile pin ← label or escape]
  D --> E{recoverable?}
  E -->|no| Z0([leave: drop illegal + receipt])
  E -->|yes| F[DET: lookup chippingway transition table]
  C -->|agree + one stage| F
  F --> G{event legal for stage?}
  G -->|no| Z1([leave: ignore + receipt])
  G -->|yes| H[DET: dispatch subgraph for stage]
  H --> I{subgraph returned advance?}
  I -->|no / hold| Z2([leave: stay + receipt])
  I -->|yes + next_stage| J[DET: flip workflow:* + rewrite pin]
  J --> K[DET: audit / analytics receipt]
  K --> Z3([leave: advanced])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  class B,D,F,H,J,K det
  class Z0,Z1 bad
```

## Transition table (compose)

| From | Event / predicate | To | Who flips |
|------|-------------------|----|-----------|
| open issue / none | poll claim | `decomposing` | orchestrator |
| `decomposing` | decompose SO ok | `ready` | orchestrator |
| `ready` | job start | `implementing` | orchestrator |
| `implementing` | PR open | `validating` | orchestrator |
| `validating` | review changes + budget | `fixing` | orchestrator |
| `fixing` | re-enter implement | `implementing` | orchestrator |
| `validating` | review OK | `documenting` | orchestrator |
| `documenting` | docs done | `in_review` | orchestrator |
| `in_review` | human merge | `done` | orchestrator |
| `*` | human pause | `paused` | człowiek / orch. |
| `*` | needs answer | `question` | orch. |
| `*` | oversized lines | `decomposing` | orchestrator |
| `*` | conflict cap | `paused` / `question` | orchestrator |

## Notes

- **chippingway DNA.** Label + pinned JSON na issue — nie pamięć agenta, nie czat.
- **Orchestrator owns advance.** Agent nigdy nie routuje; SO zwraca enum, skrypt mapuje na tabelę.
- **Handoff:** `{stage, issue_id, pin, next?}` albo `{drop|ignore}`.
