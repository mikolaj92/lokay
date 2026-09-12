# Subgraph: validate-fix

**Theme:** ReviewAgent (Codex) → fixing bounded albo documenting → in_review.  
**Mode mix:** AGENT review + DET cap / label advance.

## Flow

```mermaid
flowchart TD
  A([enter: stage=validating|documenting]) --> B{stage?}
  B -->|validating| C[AGENT: ReviewAgent pass]
  C --> D{verdict}
  D -->|changes + rounds < MAX| E[DET: label+pin → fixing]
  E --> F([leave: re-enter implementing])
  D -->|cap exceeded| G([leave: handoff hitl])
  D -->|OK| H[DET: label+pin → documenting]
  B -->|documenting| H
  H --> I[DET: polish receipt + label → in_review]
  I --> J([leave: advance in_review + HITL ping])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef ag fill:#2a2a1a,stroke:#b8a03a,color:#fff8e8
  class E,H,I det
  class C ag
```

## Notes

- **MAX_CONFLICT_ROUNDS** circuit breaker → paused/question.
- **Review ≠ merge.** Werdykt SO; flip robi orchestrator.
- **Handoff:** `{in_review:true}` albo `{fixing→implementing}`.
