# Subgraph: ticket

**Theme:** przetworzenie ticketu w kontekście → stabilny payload.  
**Mode mix:** DET normalize; opcjonalnie lekki AGENT gdy ticket niejasny.

## Flow

```mermaid
flowchart TD
  A([enter: job_ref]) --> B[DET: load ticket + links]
  B --> C[DET: normalize fields — id, title, acceptance]
  C --> D{ticket actionable?}
  D -->|no| E[DET: skip / requeue / exit]
  E --> Z0([leave: not actionable])
  D -->|yes| F{context unclear?}
  F -->|optional yes| G[AGENT: light clarify / scope note]
  F -->|no / default| H[DET: build ticket payload]
  G --> H
  H --> I([leave: ticket ready])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class B,C,E,H det
  class G agent
```

## Notes

- **Clean stage name: ticket.** Process the issue in context — nothing else lives here.
- **Normalize once.** Title, ID, acceptance hints, links become a stable payload for implement.
- **Light clarify is optional.** Default path skips AGENT; only when acceptance is ambiguous.
- **Not epic decomposition.** One actionable ticket or exit — optimistic and thin.
- **Handoff contract.** Output = `{ticket, acceptance, links, base_ref}` for implement.
