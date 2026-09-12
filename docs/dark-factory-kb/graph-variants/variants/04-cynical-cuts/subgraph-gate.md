# Subgraph: gate

**Theme:** CI → critical review → merge policy. Koniec albo pętla do code-to-pr.  
**Mode mix:** AGENT SO review; DET CI + policy. Osobny QA-agent = CUT. pr_repair = CUT.

## Flow

```mermaid
flowchart TD
  A([enter: PR open]) --> B[DET: wait CI]
  B --> C{CI green?}
  C -->|no| R([leave: changes → code-to-pr])
  C -->|yes| D[AGENT SO: critical review]
  D --> E{verdict}
  E -->|reject / changes| R
  E -->|approve| F{MergePolicy DET}
  F -->|Off| G([leave: PR open — human merges])
  F -->|Classify low / Always| H[DET: merge]
  F -->|Classify high| G
  H --> I([leave: merged])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class B,F,H det
  class D agent
```

## Notes

- **CI jest bramką DET.** Agent nie „override’uje” czerwonego builda.
- **Review = osobna rola.** Nie ten sam seat co implement. Structured: `{verdict, reasons[], risk}`. `reasons` *są* niewygodnymi pytaniami — nie potrzeba drugiego węzła „QA strategy”.
- **pr_repair CUT.** `changes` / `reject` → top-level wraca do code-to-pr. Bez osobnego fixera z max_attempts theatre w tym podgrafie.
- **Merge Policy Off default.** Skutek klepacza = otwarty PR. Always tylko gdy CI jest wyrocznią i risk=low.
- **CUT:** apply-labels ceremony, branch cleanup, per-ticket human-architecture stage, approve-bot rubber stamp bez reasons.
- **Handoff:** `{merged:true, sha}` | `{merged:false, left_open:true}` | `{merged:false, feedback}` → re-implement.
