# Subgraph: pr-ceiling

**Theme:** code-cleanup → docs → `create-pr`; stop na human review (MergePolicy Off).  
**Mode mix:** DET spine; opcjonalny cienki LLM docs leaf; HITL na merge.

## Flow

```mermaid
flowchart TD
  A([enter: verify pass]) --> B[DET: code-cleanup scripts]
  B --> C{docs leaf needed?}
  C -->|yes| D[AGENT SO: thin docs touch — optional]
  C -->|no| E[DET: create-pr template]
  D --> E
  E --> F[DET: open PR Closes #N / ai branch]
  F --> G{MergePolicy?}
  G -->|Off| H([leave: PR open — human review])
  G -->|Classify| I[DET/SO: classify risk]
  I -->|low + CI green| J[DET: merge]
  I -->|high| H
  G -->|Always + green| J
  J --> K([leave: merged])
  H --> L{human outcome?}
  L -->|approve / merge| J
  L -->|changes requested| M([leave: re-queue implement via watchdog])
  L -->|reject| N([leave: skip / close])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  classDef hitl fill:#2a2a1a,stroke:#b8a03a,color:#fff8e8
  class B,E,F,I,J det
  class D agent
  class H,L hitl
```

## Notes

- **Coder ceiling = open PR.** Jak DAGent: fabryka kończy na PR for human review — nie lights-out merge.
- **Default MergePolicy = Off.** Zgodne z KLEPACZ / ready-for-agent; Classify/Always to jawne warianty DET.
- **Cleanup/docs nie są orkiestracją.** Skrypty + opcjonalny wąski SO; nie „agent decyduje czy w ogóle robić PR”.
- **Branch convention.** `ai/issue-N` (lub hostowy odpowiednik DAGent); K=1 per ticket/spec.
- **Reviewer path.** Krytyczny `pr_review` specialist może biec *przed* create-pr (DAG edge) albo jako osobny pass po otwarciu — zawsze osobne siedzenie od implement.
- **Handoff contract.** `{pr_url, number, head, merge_policy, state: open|merged|changes}`.
