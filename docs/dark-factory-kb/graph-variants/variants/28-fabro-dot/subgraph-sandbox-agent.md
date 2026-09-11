# Subgraph: sandbox-agent

**Theme:** `box` / `tab` — **jedyny** slot LLM; tools **tylko w sandboxie**; nie router.  
**Mode mix:** AGENT leaf only. Engine decyduje *kiedy*; sandbox izoluje tool loop.

## Flow

```mermaid
flowchart TD
  A([enter: box/tab scheduled]) --> B[DET: ensure sandbox up]
  B --> C[DET: load prompt + schema + ticket_ctx]
  C --> D[DET: enforce timeout / max_tokens / tool budget]
  D --> E{leaf kind?}
  E -->|tab plan| P[AGENT SO: plan files / tests / stop_if]
  E -->|box implement| I[AGENT tools IN sandbox: edit / bash]
  E -->|tab review| R[AGENT SO: critical review verdict]
  E -->|box bounded_fix| F[AGENT tools IN sandbox: fix from failure_log]
  P --> G{ok structured / outcome?}
  I --> G
  R --> G
  F --> G
  G -->|succeeded| OK[DET: write stage outcome + context]
  G -->|failed / ok false| NO[DET: set failure_reason enum]
  OK --> OUT([leave: resume engine-routes])
  NO --> OUT
  D -->|budget hard stop| KILL[DET: fail leaf]
  KILL --> OUT
  B -->|sandbox provision fail| KILL

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class B,C,D,OK,NO,KILL det
  class P,I,R,F agent
```

## Notes

- **Sandbox leaf, not brain.** Model nie ewaluuje edge conditions, nie wybiera `exit`, nie merjuje, nie przestawia label FSM.
- **Providers.** `docker` (default) | `local` | `daytona` — tool bash/edit tylko wewnątrz; host merge/gh zostaje w `parallelogram` poza agentem (albo świadomie w sandboxie z network policy).
- **box vs tab.** `box` = multi-turn + tools (implement/repair). `tab` = one-shot prompt bez tools (plan/review SO) — mniejsza entropia, łatwiejszy audit.
- **Reviewer ≠ implementer.** Osobne węzły / osobne sesje; nigdy self-stamp. Opcjonalnie `thread_id` tylko w cluster implement — nie łączyć z review.
- **Meat ≡ AI.** Ten sam leaf seat; silnik nie rozróżnia kto wypełnił outcome.
- **ok:false / failed bez limbo.** underspecified | too_large | dangerous | cant_comply → engine bierze edge Fix/skip/exit.
- **Handoff contract.** Leave = `{node_id, outcome, context_updates?, usage}` → engine-routes.

## Structured output (skrót)

```json
{ "ok": true, "goal": "...", "files": ["..."], "test_command": "...", "non_goals": ["..."], "stop_if": ["auth","migration"] }
```

```json
{ "ok": true, "summary": "...", "files_touched": ["..."], "tests_run": true }
```

```json
{ "verdict": "approve"|"changes"|"reject", "reasons": ["..."], "risk": "low"|"high" }
```
