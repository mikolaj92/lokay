# Subgraph: classify-so

**Theme:** AGENT structured output **tylko gdy MergePolicy = Classify**. Advisory risk — nigdy merge.  
**Mode mix:** AGENT SO gated + DET risk rules po SO.

## Flow

```mermaid
flowchart TD
  A([enter: policy == Classify]) --> G{gate: still Classify?}
  G -->|no — Off/Always leaked| X[DET: abort SO — misconfig]
  X --> Z([leave: error / fail-closed])
  G -->|yes| B{invoke classify SO?}
  B -->|skip / thin config| C[DET: risk from size/paths/labels only]
  B -->|yes| D[AGENT SO: classify risk leaf]
  D --> E{SO ok?}
  E -->|false / timeout| C
  E -->|true| F[DET: merge SO.risk + size/paths/labels]
  C --> H{DET risk low?}
  F --> H
  H -->|low| L([leave: classify→low → verdict-exec])
  H -->|high| Hi([leave: classify→high → verdict-exec hold])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  classDef stop fill:#2a1a1a,stroke:#a05050,color:#ffe8e8
  class G,B,C,F,H,X det
  class D agent
  class Z stop
```

## Notes

- **Hard gate.** Ten podgraf **istnieje wyłącznie dla Classify**. Off / Always nigdy tu nie wchodzą (policy-star nie routuje). Podwójny check na wejściu = fail-closed przy misconfig.
- **SO ≠ merge.** Kontrakt: `{risk: low|high, reasons[], paths_of_concern[]}` — advisory. Autorzyzacja merge zostaje w DET + verdict-exec.
- **Opcjonalność.** Repo może mieć Classify bez wołania agenta (same reguły DET). SO jest *dozwolone* tylko tu — nie *obowiązkowe*.
- **Nie LLM classifier gałki.** Model nie ustawia Off/Always. Gałka już jest Classify; SO tylko szacuje ryzyko PR.
- **High → hold bias.** `risk:high` / chronione ścieżki (auth, billing, schema) → hold dla człowieka (SOUL: trudne decyzje zostają).
- **Handoff.** `{policy: Classify, risk: low|high, reasons, pr_url}` → subgraph-verdict-exec.
