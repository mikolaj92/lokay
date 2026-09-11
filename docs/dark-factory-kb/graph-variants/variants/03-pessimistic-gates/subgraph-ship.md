# Subgraph: ship

**Theme:** implement → lokalny test → commit → push → open PR. Jedyna entropia kodu + DET git.  
**Mode mix:** AGENT SO implement; reszta DET. Fail-closed na czerwonym teście / push fail.

## Flow

```mermaid
flowchart TD
  A([enter: issue + branch]) --> B[DET: re-assert clean worktree + label still present]
  B --> C{ok?}
  C -->|no| X([leave: fail → failure-escape])
  C -->|yes| D[AGENT SO: implement ticket]
  D --> E{SO ok + files changed?}
  E -->|ok:false / empty| X
  E -->|ok| F[DET: local test / lint gate]
  F --> G{green?}
  G -->|red| H{repair budget left?}
  H -->|yes ≤1| I[AGENT SO: bounded local repair]
  I --> F
  H -->|exhausted| X
  G -->|green| J[DET: commit]
  J --> K[DET: push origin]
  K --> L{push ok?}
  L -->|no| X
  L -->|yes| M[DET: open PR template]
  M --> N{PR created?}
  N -->|no| X
  N -->|yes| O([leave: PR open])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  class B,F,J,K,M det
  class D,I agent
  class X bad
```

## Notes

- **Re-assert before code.** Pessimista zakłada, że między preflight a ship coś się zmieniło (dirty, label). Drugi check DET.
- **Implement = AGENT SO.** Structured: `{ok, summary, files[]}`. `ok:false` → escape, nie „spróbuj innego modelu”.
- **Lokalny test jest bramką.** Czerwony bez zielonego po max 1 bounded repair → escape `local_test_red`. Nie otwieraj PR na czerwono.
- **Jeden bounded repair w liściu.** Nie zagnieżdżony SDLC, nie osobny pr_repair subgraph tutaj.
- **Push / open PR fail = escape.** Sieć, rights, template — DET report + failure-escape. Agent nie maskuje.
- **One ticket, one PR.** K=1 kontynuacja z preflight.
- **Handoff:** `{pr_url, branch, head_sha}` albo `{fail:true, reason}` → failure-escape.
