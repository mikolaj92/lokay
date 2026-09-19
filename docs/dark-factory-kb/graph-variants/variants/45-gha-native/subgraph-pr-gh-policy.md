# Subgraph: pr-gh-policy

**Theme:** job `pr` — `gh pr create` + MergePolicy.  
**Mode mix:** DET (+ HITL gdy Off).

## Flow

```mermaid
flowchart TD
  A([enter: test+code artifacts]) --> D[DET: download artifacts]
  D --> PR[DET: gh pr create Closes N]
  PR --> M{MergePolicy}
  M -->|Off| H([PR open — human])
  M -->|Classify/Always + green| MG[DET: gh pr merge]
  MG --> DONE([merged])
  H --> DONE

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class D,PR,MG det
```

## Notes

- Default Off.
- Merge tylko przez `gh` + policy — nie z liścia code.
