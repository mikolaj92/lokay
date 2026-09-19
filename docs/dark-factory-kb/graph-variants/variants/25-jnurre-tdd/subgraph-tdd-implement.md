# Subgraph: tdd-implement

**Theme:** implement w fresh worktree pod TDD — `AGENT_TEST_COMMAND` jest bramką DET przed jakimkolwiek PR.  
**Mode mix:** AGENT SO implement (+ opc. 1× local repair); worktree / test / git = DET.

## Flow

```mermaid
flowchart TD
  A([enter: agent:implement / revision reentry]) --> B[DET: fresh worktree + install K=1]
  B --> C{cell ready?}
  C -->|no| X([leave: agent:needs-info])
  C -->|yes| D[AGENT SO: implement per plan_ref — red→green]
  D --> E{SO ok + files?}
  E -->|ok:false / empty| X
  E -->|ok| F[DET: run AGENT_TEST_COMMAND]
  F --> G{green?}
  G -->|red| H{local repair budget ≤1?}
  H -->|yes| I[AGENT SO: bounded local repair]
  I --> F
  H -->|no| X
  G -->|green| J[DET: commit + push branch]
  J --> K([leave: handoff adversarial-review])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  class B,F,J det
  class D,I agent
  class X bad
```

## Notes

- **TDD first (jnurre).** Implementer ma pisać pod testy; **niezależnie** od intencji modelu, dispatch **zawsze** odpala `AGENT_TEST_COMMAND` jako gate. Czerwone = nie idziemy do review/PR.
- **Fresh worktree.** Self-hosted sandbox-pal: jeden ticket → jedna komórka; brak współdzielonego dirty tree. Bot PAT tylko do push/PR API.
- **Agent fills code slot only.** Structured `{ok, summary, files[], tests_touched?}`. Nie otwiera PR, nie ustawia `agent:pr-open`, nie merguje.
- **Bounded local repair.** Max 1 lokalna poprawka na czerwony test przed escape — osobno od revision cap w review (tam circuit breaker).
- **Re-entry from `agent:revision`.** Ten sam podgraf; attempt counter żyje w label/metadata issue, nie w „pamięci agenta”.
- **Handoff:** `{branch, head_sha, test_receipt}` → adversarial-review (PR może powstać tuż przed lub tuż po review — w kanonie jnurre: review loop, potem `agent:pr-open`).
