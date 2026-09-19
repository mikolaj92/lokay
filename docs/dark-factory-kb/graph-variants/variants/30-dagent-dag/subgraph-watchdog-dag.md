# Subgraph: watchdog-dag

**Theme:** explicytny TypeScript DAG + watchdog `getNextAvailable` — orkiestracja bez LLM.  
**Mode mix:** 100% DET. Zero LLM.

## Flow

```mermaid
flowchart TD
  A([enter: pipeline:init]) --> B[DET: load/create _STATE.json]
  B --> C[DET: bind ticket_id / spec_ref + DAG nodes]
  C --> D[DET: while running]
  D --> E[DET: getNextAvailable batch]
  E --> F{batch empty?}
  F -->|yes + terminal ok| G([leave: ready pr-ceiling / done path])
  F -->|yes + blocked/exhausted| H([leave: idle / escalate])
  F -->|no| I{node kind?}
  I -->|specialist box| J([yield: specialist-llm])
  I -->|verify / push / ci| K([yield: verify-heal])
  I -->|cleanup / create-pr| L([yield: pr-ceiling])
  J -->|write node result| M[DET: update readiness + checkpoint]
  K -->|write node result| M
  L -->|write node result| M
  M --> D

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef store fill:#1a1a2a,stroke:#6a6ab8,color:#e8e8ff
  class B,C,D,E,M det
  class B store
```

## Notes

- **Graph-is-code.** Topologia DAG (edges + prerequisites) żyje w TS / deklaratywnym JSON — nie w prompcie „zrób następny krok”.
- **`getNextAvailable` = scheduler.** Wybiera węzły z spełnionymi deps i wolnym slotem; parallel batch OK gdy DAG na to pozwala (klepacz: zwykle wąski łańcuch K=1).
- **`_STATE.json` = source of truth.** Restart procesu = wczytaj stan; context window modelu nie jest stanem misji.
- **Watchdog nie myśli.** Brak tool-calling orkiestratora; brak LLM przy wyborze batcha.
- **Klepacz bind.** Stage ids: `plan_issue`, `implement`, `push_code`, `poll_ci`, `verify`, `triage_reset`, `create_pr`, `pr_review` — nie research→SSG theatre.
- **Handoff contract.** Yield = `{node_ids[], kind, state_ref, attempt}`; resume = `{node_id, ok, artefact_ref, error?}`.
