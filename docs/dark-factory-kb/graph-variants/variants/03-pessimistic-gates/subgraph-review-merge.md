# Subgraph: review-merge

**Theme:** critical review → merge policy. Fail-closed na reject / high-risk / czerwonym re-check.  
**Mode mix:** AGENT SO review; DET merge policy + CI re-assert.

## Flow

```mermaid
flowchart TD
  A([enter: PR + CI green]) --> B[DET: re-fetch CI — still green?]
  B --> C{green?}
  C -->|no| X([leave: fail → failure-escape / or back ci-babysit])
  C -->|yes| D[AGENT SO: critical review]
  D --> E{verdict}
  E -->|reject| X2([leave: fail → failure-escape reason=review_reject])
  E -->|changes| R([leave: changes → ship])
  E -->|approve| F[DET: risk from SO + labels]
  F --> G{MergePolicy}
  G -->|Off| H([leave: left_open — human merges])
  G -->|Classify| I{risk low + CI green?}
  I -->|no| H
  I -->|yes| J[DET: merge]
  G -->|Always| K{risk high?}
  K -->|yes| H
  K -->|no| J
  J --> L{merge ok?}
  L -->|conflict / protected| X3([leave: fail → failure-escape reason=merge_blocked])
  L -->|ok| M([leave: merged])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  class B,F,G,I,J,K det
  class D agent
  class X,X2,X3 bad
```

## Notes

- **CI re-assert.** Między babysit a merge CI mógł spaść (flake, force-push). Pessimista sprawdza jeszcze raz.
- **Review = osobna rola.** Nie ten sam seat co implement. SO: `{verdict, reasons[], risk}`. `reasons` = niewygodne pytania QA w tym ticku.
- **Reject ≠ limbo.** `review_reject` → failure-escape z receipt. Changes → z powrotem do ship (bounded na top-level).
- **MergePolicy Off default.** Skutek klepacza często = otwarty PR. Always nigdy przy `risk=high`.
- **Merge conflict = escape.** Nie agent „rozwiąż konflikt w monolicie”.
- **No separate QA-strategy AGENT.** Strategia periodyczna człowieka; w ticku wystarczą `reasons[]`.
- **Handoff:** `{merged:true, sha}` | `{merged:false, left_open:true}` | `{merged:false, feedback}` → ship | `{fail:true, reason}`.
