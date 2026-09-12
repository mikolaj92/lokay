# Subgraph: code-to-pr

**Theme:** zaimplementuj → przetestuj → commit → push → otwórz PR.  
**Mode mix:** jeden AGENT SO (implement); reszta DET. Plan = CUT.

## Flow

```mermaid
flowchart TD
  A([enter: issue + branch]) --> B[AGENT SO: implement]
  B --> C{ok?}
  C -->|false| X([leave: skip / fail])
  C -->|true| D[DET: run test_command from ticket]
  D --> E{green?}
  E -->|red, retries left| B
  E -->|red, max N=1 exhausted| X
  E -->|green| F[DET: commit]
  F --> G[DET: push origin]
  G --> H[DET: open PR Closes issue]
  H --> I([leave: PR open])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class D,F,G,H det
  class B agent
```

## Notes

- **Plan leaf CUT.** Ticket mówi CO i JAK sprawdzić. Jeśli nie — wróć do pick/skip. Planowanie nie otwiera PR.
- **Jeden AGENT liść.** `implement` ze structured output: `{ok, summary, files_touched}` albo `{ok:false, reason}`. Fail = exit, nie limbo.
- **Test z ticketa.** DET komenda. Czerwony bez komendy weryfikacji = nie bierz ticketa (pick już to odsiało).
- **Bounded retry N=1.** Nie osobny `repair_code` subgraph. Druga czerwień = leave fail. Escapism zabija cynizm.
- **Commit/push/open PR = DET.** Message z ID + summary. Template PR. Zero agent-novelisty w git plumbing.
- **CUT:** multi-commit product loop, local-check ceremony poza `test_command`, file-breakdown agent, „ulepsz po drodze”.
- **Handoff:** `{pr_url, branch, head_sha}` albo fail/skip.
