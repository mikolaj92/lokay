# Subgraph: temporal-spine

**Theme:** Temporal-ish state machine = deterministyczny szkielet; worker state = źródło prawdy.  
**Mode mix:** DET only. Zero LLM w ciele FSM.

## Flow

```mermaid
flowchart TD
  A([enter: board ticket ready]) --> B[DET: start Temporal-ish run]
  B --> C[DET: bind ticket id + run id]
  C --> D[(run state / event history)]
  D --> E[DET: schedule next state id]
  E --> F{state?}
  F -->|size / triage| SIZE[DET: size ticket]
  SIZE --> D
  F -->|adapter I/O| AD([yield: adapter-plane])
  F -->|agent seat| LEAF([yield: agent-leaf])
  F -->|prove / tests / review / merge| PRV([yield: prove-review-merge])
  F -->|terminal ok| DONE([leave: done])
  F -->|stall / budget| ESC([leave: human evaluate / escalate])
  AD -->|adapter result recorded| D
  LEAF -->|leaf result recorded| D
  PRV -->|gate result recorded| D
  E --> G{history bloated?}
  G -->|yes| H[DET: continue-as-new / compact]
  H --> D
  G -->|no| F

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef store fill:#1a1a2a,stroke:#6a6ab8,color:#e8e8ff
  class B,C,E,SIZE,H det
  class D store
```

## Notes

- **Replay-safe.** Ciało FSM czyta tylko zapisany stan + wyniki adapterów/liści. Żadnych LLM / losowych zegarów w transitions (Temporal nondeterminism mindset).
- **Orkiestrator nie myśli.** `schedule next state id` = stała kolejność openfactory (size → box_prove → plan → agent → tests → review → merge_policy) + diamondy budżetu / hold.
- **Durability ≠ agent memory.** Context window modelu nie jest stanem misji. Restart workera = replay / resume run state.
- **One run per ticket.** K=1 occupancy egzekwowane przed startem lub jako pierwszy DET krok; nie fan-out katalogu w środku runu.
- **Panel UI ≠ router.** :8787 pokazuje stany i stall options; człowiek ewaluuje — model nie wybiera lane.
- **Handoff contract.** Yield adapter-plane = `{state_id, axis, op, idempotency_key, input_ref}`; yield agent-leaf = `{state_id, engine, prompt_ref, schema, ticket_ctx, attempt}`; yield prove-review-merge = `{gate, sandbox_ref, pr_ref?, policy}`.
