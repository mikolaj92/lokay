# Subgraph: hub-det-stages

**Theme:** Hub-owned stage machine — triggers, `run`/`gate`, `on_enter` bez modelu.  
**Mode mix:** DET spine. Chat markers opcjonalne UX, nie jedyny dowód.

## Flow

```mermaid
flowchart TD
  A([enter: published entry stage]) --> B[DET: eval skip_if / skip_unless labels]
  B -->|go_to terminal skip| SKIP([leave: idle skipped])
  B -->|continue| C[DET: on_enter move_issue / labels / notify]
  C --> D{stage needs leaf?}
  D -->|inject / plan / implement| LEAF([yield: sandbox-agent-leaf])
  D -->|run command| R[DET: sandbox run → JSON output]
  R --> G{gate pass/fail?}
  G -->|pass| E[DET: gate_result → next stage]
  G -->|fail| F[DET: gate_result fail branch]
  F --> LEAF
  E --> H{hub trigger?}
  H -->|pr_conditions ci+reviews| LIFE([yield: lifecycle-cleanup])
  H -->|pr_merged / pr_closed| LIFE
  H -->|plan_gate schema ok| LEAF
  H -->|message_contains UX only| LEAF
  LEAF --> C

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class B,C,R,E,F det
```

## Notes

- **Hub owns next stage.** `pr_merged`, `pr_closed`, `pr_conditions` (`ci`, `reviews`, `quiet_for`), `gate_result`, `output_matches`, `judge_verdict` (transition DET; verdict z wcześniejszego leaf) — Server awansuje bez NLP.
- **`run` + `gate`.** Komenda w sandboxie drukuje JSON; gate porównuje path/values. Preferuj to nad `[DONE]` jako jedyny dowód walidacji.
- **`plan_gate: true`.** Schema-only check `plan.json` → jeden tor akceptacji; wyłącza freeform chat-approve dla tego pipeline (bez double-approve).
- **`on_enter` bez czatu.** `move_issue`, `add_labels`/`remove_labels`, `merge_pr`, `notify`, `close_issue` — hub, nie model.
- **Handoff contract.** Yield leaf = `{stage_id, inject_text, outputs, creds_ref}`; yield lifecycle = `{pr_ref, policy, terminal_candidates}`.
