# Subgraph: box-llm

**Theme:** `shape=box` — LLM **tylko** wypełnia węzeł (structured output).  
**Mode mix:** AGENT SO leaves. Zero git, zero routingu, zero tool-calling orkiestratora.

## Flow

```mermaid
flowchart TD
  A([enter: node_id + schema]) --> B{which box?}
  B -->|plan_issue| C[AGENT SO: plan_issue]
  B -->|implement / repair_code| D[AGENT SO: implement]
  B -->|pr_review| E[AGENT SO: pr_review]
  C --> F{ok?}
  D --> F
  E --> G{verdict?}
  F -->|ok:true| H[DET: write leaf result to checkpoint]
  F -->|ok:false| I[DET: reason enum → skip/escape]
  G -->|approve| H
  G -->|changes| J[DET: attach feedback for re-enter implement]
  G -->|reject / high| I
  H --> K([leave: resume det-walk])
  I --> L([leave: skip / no limbo])
  J --> K

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class H,I,J det
  class C,D,E agent
```

## Notes

- **LLM fills nodes only.** Box dostaje prompt + JSON schema; zwraca obiekt. Nie woła „następnego toola z listy świata”.
- **Trzy liście klepacza (kanon).**
  - `plan_issue` — goal, files, test_command, non_goals, stop_if
  - `implement` / `repair_code` — summary, files_touched; max N bounded
  - `pr_review` — verdict approve\|changes\|reject + reasons + risk
- **Coder ≠ merge ≠ open_pr.** Implement nie otwiera PR i nie merjuje — to parallelogram w det-walk.
- **Reviewer ≠ implementer.** Osobny box / osobne siedzenie; nigdy self-stamp.
- **ok:false bez limbo.** underspecified \| too_large \| dangerous \| cant_comply → skip; park labels wyłączone.
- **Meat ≡ AI.** Człowiek może wypełnić ten sam schema ręcznie; runner nie wie.
- **Handoff contract.** Output = `{node_id, so_payload, resume_edge}` albo `{ok:false, reason}` dla det-walk.

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
