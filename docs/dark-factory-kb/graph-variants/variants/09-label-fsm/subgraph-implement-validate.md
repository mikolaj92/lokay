# Subgraph: implement-validate

**Theme:** implement slot w fresh worktree → lokalny test DET → push/PR → etykieta validating.  
**Mode mix:** AGENT SO implement (+ opc. 1× local repair); reszta DET.

## Flow

```mermaid
flowchart TD
  A([enter: stage implementing]) --> B[DET: fresh worktree + install K=1]
  B --> C{cell ready?}
  C -->|no| X([leave: needs-human])
  C -->|yes| D[AGENT SO: implement ticket / plan_ref]
  D --> E{SO ok + files?}
  E -->|ok:false / empty| X
  E -->|ok| F[DET: local test / lint gate]
  F --> G{green?}
  G -->|red| H{repair budget ≤1?}
  H -->|yes| I[AGENT SO: bounded local repair]
  I --> F
  H -->|no| X
  G -->|green| J[DET: commit + push]
  J --> K[DET: open PR Closes N]
  K --> L{PR ok?}
  L -->|no| X
  L -->|yes| M[DET: label → workflow:validating]
  M --> N([leave: PR open + validating])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  class B,F,J,K,M det
  class D,I agent
  class X bad
```

## Notes

- **Fresh worktree.** chippingway / ready-for-agent: jeden ticket → jedna komórka; brak współdzielonego dirty tree.
- **Agent fills code slot only.** Structured `{ok, summary, files[]}`. Nie otwiera PR, nie ustawia labeli, nie merguje.
- **Lokalny test = bramka DET.** Czerwony po max 1 repair → escape. Nie PR na czerwono.
- **Open PR = DET.** Template + `Closes #N`; po sukcesie **skrypt** ustawia `workflow:validating` (jnurre `agent:pr-open` alias mapuje tu albo na `pr-open` po approve — w tej kompozycji validating najpierw).
- **Re-entry from fixing.** Ten sam podgraf; counter fix żyje w labels/comment metadata, nie w „pamięci agenta”.
- **Handoff:** `{pr_url, branch, head_sha}` → review-fix.
