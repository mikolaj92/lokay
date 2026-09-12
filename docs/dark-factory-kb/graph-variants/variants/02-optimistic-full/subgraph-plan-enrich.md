# Subgraph: plan-enrich

**Theme:** lekki plan / file hints / acceptance map — modular enrich przed kodem.  
**Mode mix:** AGENT SO (plan only); DET wrap. Bogatszy niż thin (01), nadal wąski liść.

## Flow

```mermaid
flowchart TD
  A([enter: ticket + branch]) --> B[DET: load ticket payload + repo hints]
  B --> C[AGENT SO: plan-enrich]
  C --> D{SO ok?}
  D -->|ok:false rare| E[DET: fallback thin plan from title]
  E --> F[DET: attach plan artifact to ticket/PR body draft]
  D -->|ok:true| F
  F --> G([leave: plan ready])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class B,E,F det
  class C agent
```

## Notes

- **Plan writes no product code.** Tylko structured plan: kroki, pliki podejrzane, ryzyka, test hints.
- **Default ON in optimistic-full.** Wariant 01 skipuje plan; tu plan jest pierwszym-class modularnym krokiem (współpracujący ticket zwykle ma sens).
- **Fallback thin.** Jeśli SO `ok:false` — DET skleja minimalny plan z tytułu/acceptance; nie escape theatre.
- **Meat ≡ AI.** To samo siedzenie plan-only.
- **Handoff:** `{plan: {steps[], files[], risks[], test_hints[]}, ticket, branch}`.
