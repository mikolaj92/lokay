# Subgraph: coder-ceiling

**Theme:** łańcuch do otwartego PR — **coder never merges**. Sufit = `PR open Closes #N`.  
**Mode mix:** DET spine + AGENT implement leaf; zero merge auth.

## Flow

```mermaid
flowchart TD
  A([enter: harness tick]) --> B[DET: list issues label ready-for-agent]
  B --> C{one issue?}
  C -->|none| IDLE([leave: idle])
  C -->|yes| D[DET: fresh worktree + install K=1]
  D --> E[AGENT SO: implement leaf]
  E --> F{ok?}
  F -->|false| SKIP([leave: skip + receipt])
  F -->|true| G[DET: verify / commit / push]
  G --> H{local green?}
  H -->|no, budget out| SKIP
  H -->|yes| I[DET: open PR Closes N]
  I --> J([leave: PR open — handoff to policy-star])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  classDef stop fill:#2a1a1a,stroke:#a05050,color:#ffe8e8
  class B,D,G,I det
  class E agent
  class IDLE,SKIP stop
```

## Notes

- **Reuse ready-for-agent.** Label = start; fresh worktree; headless agent w liściu. Feeder pod ★ MergePolicy — nie osobna religia.
- **Coder ≠ merge.** Ani meat, ani AI w tym podgrafie nie woła merge. Brak przycisku, brak toola, brak „skoro CI zielone to zmergujemy w implementerze”.
- **Handoff.** Output = `{pr_url, issue_n, branch, commit_shas}` → **subgraph-policy-star**. Albo `{skip, reason}`.
- **Meat ≡ AI.** To samo siedzenie AGENT; graf bez zmian (SOUL).
- **Bounded.** Fail / underspecified / blocked_path → skip + receipt, nie limbo.
