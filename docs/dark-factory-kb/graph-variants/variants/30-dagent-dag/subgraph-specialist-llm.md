# Subgraph: specialist-llm

**Theme:** węzły specjalistów — **jedyny** sink LLM; structured output, zero routingu.  
**Mode mix:** AGENT SO leaves. Watchdog / git / CI = poza tym podgrafem.

## Flow

```mermaid
flowchart TD
  A([enter: node_id + schema + ticket_ctx]) --> B{which specialist?}
  B -->|plan / design| C[AGENT SO: plan_issue]
  B -->|implement / code| D[AGENT SO: implement]
  B -->|triage diagnostic| E[AGENT SO: TriageDiagnostic]
  B -->|pr_review| F[AGENT SO: pr_review]
  C --> G{ok?}
  D --> G
  E --> H{reset advice?}
  F --> I{verdict?}
  G -->|ok:true| J[DET: write artefact → _STATE.json]
  G -->|ok:false| K[DET: reason enum → skip/escape]
  H -->|bounded reset ids| J
  H -->|give up| K
  I -->|approve| J
  I -->|changes| L[DET: attach feedback → re-queue implement]
  I -->|reject / high risk| K
  J --> M([leave: resume watchdog])
  K --> N([leave: skip / no limbo])
  L --> M

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class J,K,L det
  class C,D,E,F agent
```

## Notes

- **LLM fills specialist nodes only.** Prompt + JSON schema → obiekt. Nie woła „następnego toola ze świata”; nie mutuje DAG.
- **Mapowanie ~12 agentów DAGent → cienkie liście klepacza.** Fazy DAGent zwijamy do: `plan_issue`, `implement` (+ opc. task-breakdown), `TriageDiagnostic`, `pr_review`. Reszta faz (deploy/docs) = DET w innych podgrafach.
- **Coder ≠ merge ≠ push.** Implement nie pushuje i nie otwiera PR — to DET w verify-heal / pr-ceiling.
- **Reviewer ≠ implementer.** Osobny specialist / osobne siedzenie; nigdy self-stamp.
- **TriageDiagnostic ≠ nieskończony heal.** Zwraca listę node_ids do resetu; limity egzekwuje verify-heal / watchdog (≤5).
- **ok:false bez limbo.** `underspecified | too_large | dangerous | cant_comply` → skip; park labels wyłączone.
- **Meat ≡ AI.** Człowiek może wypełnić ten sam schema; watchdog nie wie.
- **Handoff contract.** `{node_id, so_payload, ok}` albo `{ok:false, reason}` + opc. `{reset_node_ids[]}` dla triage.

## Structured output (skrót)

```json
{ "ok": true, "goal": "...", "files": ["..."], "test_command": "...", "non_goals": ["..."], "stop_if": ["auth","migration"] }
```

```json
{ "ok": true, "summary": "...", "files_touched": ["..."], "tests_hint": "..." }
```

```json
{ "ok": true, "diagnosis": "...", "reset_node_ids": ["implement","verify"], "stop": false }
```

```json
{ "verdict": "approve"|"changes"|"reject", "reasons": ["..."], "risk": "low"|"high" }
```
