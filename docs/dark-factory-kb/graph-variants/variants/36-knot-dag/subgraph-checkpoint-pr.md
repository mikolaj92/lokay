# Subgraph: checkpoint-pr

**Theme:** `needs_human` checkpoint + coder ceiling = open PR; MergePolicy Off.  
**Mode mix:** HITL + DET PR atoms; opcjonalny cienki runner na body/docs.

## Flow

```mermaid
flowchart TD
  A([enter: checkpoint or ship-ready]) --> B{kind?}
  B -->|needs_human| C[DET: mark checkpoint in SQLite]
  C --> D[HITL: dagain answer / chat / UI]
  D --> E[DET: record decision → kv_history]
  E --> F([leave: resume sqlite-dag])
  B -->|ship / integrate done| G[DET: ensure branch ai/issue-N]
  G --> H[DET: create-pr template Closes #N]
  H --> I{MergePolicy?}
  I -->|Off| J([leave: PR open — human review])
  I -->|Classify| K[DET/SO: classify risk]
  K -->|low + CI green| L[DET: merge]
  K -->|high| J
  I -->|Always + green| L
  L --> M([leave: merged])
  J --> N{human outcome?}
  N -->|approve / merge| L
  N -->|changes| O[DET: re-queue execute via SQLite]
  O --> F
  N -->|reject| P([leave: skip / close])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef hitl fill:#2a2a1a,stroke:#b8a03a,color:#fff8e8
  classDef stop fill:#2a1a1a,stroke:#a05050,color:#ffe8e8
  class C,E,G,H,K,L,O det
  class D,J,N hitl
  class P stop
```

## Notes

- **Checkpoint is durable.** Decyzja człowieka w SQLite — no re-asking, no context loss (dagain model).
- **Chat ≠ orchestrator.** `dagain chat` czyta tę samą bazę (status/pause/inject); nie zastępuje supervisor apply.
- **Coder ceiling = open PR.** Zgodnie z duszą: zdjąć klepanie do PR; merge = wartość ludzka / polityka.
- **Default MergePolicy = Off.** Classify/Always = jawne warianty DET na hoście klepacza.
- **K=1.** Jedna sesja / jeden goal / jeden PR; supervisor nie sieje katalogu feature’ów.
- **Handoff contract.** Checkpoint = `{node_id, question, answer?, state: waiting|resolved}`; PR = `{pr_url, number, head, merge_policy, state}`.
