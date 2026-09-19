# Subgraph: ci-babysit

**Theme:** flaky CI — poll, bounded re-run, timeout. Babysitting bez człowieka i bez limbo.  
**Mode mix:** 100% DET. Agent nie override’uje czerwonego builda.

## Flow

```mermaid
flowchart TD
  A([enter: PR open]) --> B[DET: fetch check runs]
  B --> C{all concluded?}
  C -->|pending| D{poll budget left?}
  D -->|yes| E[DET: sleep backoff]
  E --> B
  D -->|exhausted| X([leave: fail → failure-escape reason=ci_timeout])
  C -->|yes| F{all green?}
  F -->|yes| G([leave: CI green])
  F -->|red / failed| H{flaky class + re-run budget?}
  H -->|known flaky + budget| I[DET: re-run failed jobs]
  I --> B
  H -->|hard fail or budget 0| X2([leave: fail → failure-escape reason=ci_red])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  class B,E,I det
  class X,X2 bad
```

## Notes

- **Załóż flaky.** Pierwszy czerwony nie jest wyrokiem — jeśli job jest na allowlist flaky **i** zostaje budget re-run, DET odpala ponownie.
- **Bounds are sacred.** `poll_budget`, `rerun_budget`, `max_wall_clock`. Wyczerpanie → escape, nie wieczne czekanie, nie limbo label.
- **Hard fail vs flaky.** Compile / typecheck / policy check = hard. Oznaczone e2e flake = flaky. Nieznane = hard (fail-closed).
- **No AGENT in this subgraph.** Babysitting CI to skrypt. LLM nie „interpretuje logów żeby uznać za zielone”.
- **CI is oracle for merge later.** Ten podgraf tylko doprowadza do `green` albo `escape`.
- **Handoff:** `{ci:green, check_sha}` albo `{fail:true, reason: ci_timeout|ci_red, failing_checks[]}`.
