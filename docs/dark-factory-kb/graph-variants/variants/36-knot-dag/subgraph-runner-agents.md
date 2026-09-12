# Subgraph: runner-agents

**Theme:** agenty jako **runners** — świeży packet, structured propose; **zero** mutacji grafu.  
**Mode mix:** AGENT runners only. Supervisor / SQLite apply = poza tym podgrafem.

## Flow

```mermaid
flowchart TD
  A([enter: node_id + packet + role]) --> B[DET: pick runner from role pool]
  B --> C[AGENT: fresh process + packet]
  C --> D{result shape?}
  D -->|success + next| E[DET: validate proposal schema]
  D -->|fail / timeout / missing| F{promote pool?}
  D -->|needs_human signal| G[DET: wrap → checkpoint proposal]
  F -->|yes| H[DET: promote runner — next in pool]
  H --> C
  F -->|no / last stuck| I[DET: fail proposal → retry/escalate]
  E --> J{schema ok?}
  J -->|yes| K([leave: proposal → supervisor apply])
  J -->|no| I
  G --> K
  I --> L([leave: fail → sqlite-dag retry policy])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class B,E,F,G,H,I,J det
  class C agent
```

## Notes

- **Propose, don't apply.** Canonical shape (dagain-style):
  ```json
  {
    "status": "success",
    "next": {
      "setStatus": [{"id": "task-001", "status": "done"}],
      "addNodes": [{"id": "task-002", "title": "Add tests"}]
    }
  }
  ```
- **Fresh packet every time.** Goal + decyzje deps + artefakty — chirurgicznie. Brak narastającego chatu jako SoT.
- **Role pools.** np. `executor: [codexMedium, codex, claude]` — promotion on timeout / missing_result / spawn_error; cheap-first.
- **Runner ≠ orchestrator.** Nie wybiera „co dalej w całym DAGu”; może *proponować* `addNodes`, ale supervisor decyduje o apply.
- **Meat ≡ AI.** Człowiek może wypełnić ten sam packet/schema; pool entry „human” OK.
- **ok:false bez limbo.** `underspecified | too_large | dangerous | cant_comply` → fail proposal → sqlite escalate / skip.
- **Handoff contract.** `{node_id, proposal, runner_id, attempts, ok}` albo `{ok:false, reason, promote?}`.
