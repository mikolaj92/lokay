# Subgraph: hitl-exit

**Theme:** `shape=hexagon` + MergePolicy — wyjście z walka bez LLM-merge theatre.  
**Mode mix:** HITL + DET policy. Zero box LLM w decyzji merge Always przy risk=high.

## Flow

```mermaid
flowchart TD
  A([enter: PR + review payload]) --> B[DET: wait / fetch CI]
  B --> C{CI green?}
  C -->|no| D[DET: report — resume box repair or skip]
  D --> BACK([leave: changes → box-llm / det-walk])
  C -->|yes| E{review verdict?}
  E -->|changes| BACK
  E -->|reject / risk high| F[HEXAGON: human hold]
  F --> G([leave: left open — human owns])
  E -->|approve| H{MergePolicy DET}
  H -->|Off| I[HEXAGON: leave open for human]
  I --> G
  H -->|Classify| J{low risk + green?}
  J -->|no| I
  J -->|yes| K[DET: merge_commit]
  H -->|Always| L{risk high?}
  L -->|yes| I
  L -->|no| K
  K --> M[DET: close_issue + receipt]
  M --> N([leave: done Msquare])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef human fill:#2a1a3a,stroke:#8a5ab8,color:#f3e8ff
  class B,D,H,J,K,M,L det
  class F,I human
```

## Notes

- **Hexagon ≠ box.** Human gate nie jest „LLM udającym człowieka”. Off default = klepacz kończy na otwartym PR.
- **MergePolicy Off \| Classify \| Always.** Gałka DET; Always nigdy przy `risk=high` / reject.
- **CI jest wyrocznią DET.** AGENT nie nadpisuje czerwonego builda.
- **Changes → z powrotem do box implement** przez det-walk (bounded), nie osobny fat repair department.
- **NOT L5.** Ludzie odpowiadają za skutek przy Off i przy high-risk; runner tylko doprowadza do bramki.
- **Handoff contract.** `{merged:true, merge_sha}` \| `{merged:false, left_open:true}` \| `{merged:false, feedback}` → receipt / resume.
