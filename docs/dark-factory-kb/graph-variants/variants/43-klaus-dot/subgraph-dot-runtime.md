# Subgraph: dot-runtime

**Theme:** `klaus run` ładuje fixed `.dot`; runtime immutable.  
**Mode mix:** 100% DET.

## Flow

```mermaid
flowchart TD
  A([start]) --> L[DET: load pipelines/*.dot]
  L --> V{shape allowlist ok?}
  V -->|no| E([idle / config error])
  V -->|yes| W[DET: walk edges — 0 tokens]
  W --> Y([leave: next node typed])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class L,W det
```

## Notes

- Sprint-plan może emitować DOT offline; run nie mutuje grafu.
- LLM nie wybiera next node.
