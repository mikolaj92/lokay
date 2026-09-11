# Subgraph: verify-heal

**Theme:** DET push → poll-ci → testy (+ live-ui gdy host ma); bounded triage reset ≤5.  
**Mode mix:** DET majority; LLM tylko gdy watchdog odda `TriageDiagnostic` (przez specialist-llm).

## Flow

```mermaid
flowchart TD
  A([enter: ship/verify edges ready]) --> B[DET: push-code shell bypass]
  B --> C{push ok?}
  C -->|no| X[DET: fail — escalate]
  C -->|yes| D[DET: poll-ci / GHA checks]
  D --> E{CI green?}
  E -->|timeout/red| T{reset_count < 5?}
  E -->|green| F[DET: integration / host tests]
  F --> G{tests ok?}
  G -->|no| T
  G -->|yes| H{live-ui required?}
  H -->|no| I([leave: verify pass → pr-ceiling])
  H -->|yes| J[DET: Playwright live-ui]
  J --> K{ui ok?}
  K -->|yes| I
  K -->|no| T
  T -->|yes| L[DET: bump reset_count]
  L --> M([yield: specialist TriageDiagnostic])
  M -->|reset ids| N[DET: mark nodes pending in _STATE.json]
  N --> O([leave: resume watchdog])
  T -->|no| P([leave: escalate / skip — circuit open])
  X --> P

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef stop fill:#2a1a1a,stroke:#a05050,color:#ffe8e8
  class B,D,F,J,L,N,X det
  class P stop
```

## Notes

- **Shell bypass = DET.** `push-code` / `poll-ci` bez modelu (jak DAGent). Constitutional git wrappers OK.
- **Live-ui opcjonalne na hoście klepacza.** Playwright na żywym env to wzorzec DAGent; jeśli host nie ma deploy — wystarczy CI + unit/integration DET.
- **Circuit breaker ≤5.** `reset_count` w `_STATE.json`; po limicie escalate — nie „agent napraw świat”.
- **Triage jest liściem, nie orkiestratorem.** Diagnosis SO mówi *co* zresetować; watchdog *wykonuje* reset readiness.
- **Fail closed.** Czerwony CI bez budżetu → idle/escalate z komentarzem na ticket/PR draft — nie ciche limbo.
- **Handoff contract.** Pass = `{verify: ok, head_sha, checks[]}`; heal = `{reset_node_ids[], reset_count}`; exhaust = `{ok:false, reason: "circuit_open"}`.
