# Subgraph: decompose-ready

**Theme:** DecomposeAgent rozbija ticket → `workflow:ready`; oversized wraca do decomposing.  
**Mode mix:** DET intake/advance + AGENT SO slot (decompose).

## Flow

```mermaid
flowchart TD
  A([enter: stage=decomposing|ready]) --> B[DET: claim issue + ensure pin]
  B --> C{DECOMPOSE=off?}
  C -->|yes skip| D[DET: label+pin → ready]
  C -->|no| E[AGENT: DecomposeAgent SO]
  E --> F{ok + sized?}
  F -->|ok| D
  F -->|oversized / MAX_ADDED_LINES| G[DET: stay decomposing + comment]
  F -->|needs human| H([leave: handoff hitl paused/question])
  D --> I([leave: advance implementing])
  G --> J([leave: stay + receipt])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef ag fill:#2a2a1a,stroke:#b8a03a,color:#fff8e8
  class B,C,D,G det
  class E ag
```

## Notes

- **Slot only.** DecomposeAgent wypełnia plan/split SO; nie flipuje labeli.
- **Oversized → decomposing.** Limit linii = DET gate, nie LLM-judge.
- **Handoff:** `{ready:true}` → spine advance `implementing`.
