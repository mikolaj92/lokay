# Subgraph: hitl-merge

**Theme:** `in_review` + jeden ping HITL; `paused`/`question` escape; merge tylko człowiek.  
**Mode mix:** 100% DET + HITL. Zero agent-merge.

## Flow

```mermaid
flowchart TD
  A([enter: in_review|paused|question]) --> B{stage?}
  B -->|in_review| C[DET: single HITL ping]
  C --> D{human action?}
  D -->|merge| E[DET: label+pin → done]
  D -->|hold| F([leave: stay in_review])
  D -->|request changes| G[DET: → fixing / question]
  B -->|paused| H([leave: wait human unpause])
  B -->|question| I([leave: wait human answer])
  E --> J([leave: terminal done])
  G --> K([leave: handoff spine])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef hitl fill:#2a1a3a,stroke:#8f3d8f,color:#ffe8ff
  class C,E,G det
  class D,H,I hitl
```

## Notes

- **Orchestrator never merges.** Default merge policy = Off.
- **Escape obowiązkowy.** paused/question bez unbounded retry.
- **Handoff:** `{done}` albo `{wait_human}`.
