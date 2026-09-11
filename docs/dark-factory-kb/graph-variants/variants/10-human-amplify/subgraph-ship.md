# Subgraph: ship

**Theme:** implementacja → test → branch/commit/push/PR; jawny flag `arch_touch`.  
**Mode mix:** AGENT SO (jak zakodować) + DET (git/PR + detekcja arch_touch).

## Flow

```mermaid
flowchart TD
  A([enter: clean lane + ticket]) --> B[DET: normalize ticket payload]
  B --> C{underspecified?}
  C -->|yes| S([leave: skip — receipt underspecified])
  C -->|no| D[AGENT SO: plan-lite + implement]
  D --> E[DET: run local tests]
  E -->|red + repair budget| D
  E -->|red exhausted| X([leave: hold — receipt test_red])
  E -->|green| F[DET: branch + commit + push]
  F --> G[DET: open PR]
  G --> H[DET: classify arch_touch]
  H -->|paths / contracts / topology heuristics| I{arch_touch?}
  I -->|true| J([leave: PR open + arch_touch → arch-gate])
  I -->|false| K([leave: PR open → review-merge])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  class B,E,F,G,H det
  class D agent
  class S,X bad
```

## Notes

- **AGENT = tylko entropia kodu.** Narrow seat: jak zaimplementować ten ticket. Nie orkiestruje tool-callingiem całego procesu.
- **DET owns git/PR.** Branch, commit(s), push origin, open PR — skrypt. Meat ≡ AI w AGENT seat bez zmiany grafu.
- **`arch_touch` is first-class.** Heurystyki DET (zmiana publicznych API, schematów, granic pakietów, ADR-tagged paths, `ARCHITECTURE.md`, topology configs). False negative → człowiek i tak może wymusić gate; false positive → tani HUMAN glance.
- **One ticket, one PR.** K=1; bez mega-branchy. Repair loop bounded.
- **Nie przemycać architektury.** Jeśli implementacja „przy okazji” rusza kontrakt — flag musi być `true`. Arch-gate jest obowiązkowy przed merge.
- **Handoff:** `{pr, arch_touch:bool, sha}` albo `{skip|hold, reason, receipt_id}`.
