# Subgraph: merge-human

**Theme:** merge albo poprawki → przestrzeń na ludzką architekturę i QA-strategię.  
**Mode mix:** DET merge; HUMAN na architekturę i niewygodne pytania.

## Flow

```mermaid
flowchart TD
  A([enter: approved PR]) --> B[DET: apply labels / approvals]
  B --> C[DET: merge PR]
  C --> D{merge ok?}
  D -->|conflict / policy block| E[DET: report block]
  E --> F([leave: fix needed → implement])
  D -->|yes| G[DET: cleanup branch if policy]
  G --> H[HUMAN: architecture attention]
  H --> I[HUMAN: QA strategy — uncomfortable questions]
  I --> J([leave: merged + human energy spent on value])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef human fill:#2a1a3a,stroke:#8a5ab8,color:#f3e8ff
  class B,C,E,G det
  class H,I human
```

## Notes

- **Merge is DET after green review.** Labels/checks → merge script; humans intervene on conflict or policy block.
- **Fix loop is honest.** Almost always there are poprawki — leave back to implement with feedback, do not pretend otherwise.
- **Human architecture / QA is the win.** SOUL criterion: person has energy for hard decisions and "czemu tak — nie da się prościej?" because the chain already did the exhausting middle.
- **NOT replacing QA strategy.** Periodic uncomfortable questions stay; good QA engineers gain time, they do not disappear.
- **Success is merged reality.** Tip of host moves in a sensible time window — not pretty JSON without effect.
- **Handoff contract.** Output = `{merged: true, merge_sha, human_notes}` or `{merged: false, feedback}` for re-implement.
