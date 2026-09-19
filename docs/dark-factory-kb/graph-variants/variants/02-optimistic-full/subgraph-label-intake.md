# Subgraph: label-intake

**Theme:** etykieta = start → pick one → normalize ticket → branch ready.  
**Mode mix:** prawie wszystko DET. Optymista zakłada, że label jest i ludzie go trzymają.

## Flow

```mermaid
flowchart TD
  A([enter subgraph]) --> B[DET: list issues with ready-for-agent]
  B --> C{any labeled?}
  C -->|no| D[DET: idle receipt]
  D --> Z([leave: idle])
  C -->|yes| E[DET: pick one — K=1]
  E --> F[DET: normalize title / id / acceptance / links]
  F --> G[DET: derive branch name from ticket]
  G --> H[DET: checkout / create branch from base]
  H --> I([leave: ticket + branch ready])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class B,E,F,G,H,D det
```

## Notes

- **Label = start.** Zero chat pick, zero agent choose. Inżynier oznaczył → klepacz bierze.
- **Optimistic skip re-assert.** Nie zakładamy znikającego labela między pick a start (kontrast do 03). Jedna lista, jeden pick.
- **Normalize once.** Stabilny payload `{ticket, acceptance, links}` dla plan-enrich i implement-ship.
- **Branch naming DET.** `ai/<id>-<slug>` lub konwencja repo — nie agent inventuje nazw.
- **K=1.** Jeden ticket naraz; occupancy poza tym podgrafem jeśli trzeba.
- **Handoff:** `{ticket, branch, base_ref}` albo `{idle:true}`.
