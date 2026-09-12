# Subgraph: policy-star ★

**Theme:** **Merge Policy Off | Classify | Always** — gwiazda grafu. Gałka per repo z ready-for-agent; DET only.  
**Mode mix:** 100% DET routing. Tu **nie** ma LLM.

## Flow

```mermaid
flowchart TD
  A([enter: PR open Closes N]) --> B[DET: read repo MergePolicy knob]
  B --> C{Off | Classify | Always}
  C -->|Off| OFF[DET: route → human hold path]
  C -->|Always| ALW[DET: route → allowlist path]
  C -->|Classify| CLS[DET: route → classify-so then DET rules]
  OFF --> O([leave: Off → verdict-exec hold-bias])
  ALW --> W([leave: Always → verdict-exec allowlist])
  CLS --> Q([leave: Classify → subgraph-classify-so])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef star fill:#2a1a3a,stroke:#a060c0,color:#f8e8ff
  class B,OFF,ALW,CLS det
  class C star
```

## Notes

- **★ Star.** To jest hub wariantu 13. Reszta (coder, classify SO, exec) orbituje wokół tej gałki.
- **Reuse fidelity.** ready-for-agent Merge Policy: **Off / Classify / Always**. Kanon KLEPACZ — nie prompt „czy zmergować?”.
- **Default Off.** Bezpieczny start: PR otwarty, człowiek merguje.
- **Gating SO.** Tylko gałąź **Classify** wchodzi w `subgraph-classify-so`. Off i Always **pomijają** AGENT classify — zero wołań.
- **LLM nie klika.** Routing i późniejszy merge/hold są DET. Agent nie wybiera wartości gałki.
- **Handoff contract.** `{policy: Off|Classify|Always, pr_url, issue_n}` → classify-so (tylko Classify) lub wprost verdict-exec.
