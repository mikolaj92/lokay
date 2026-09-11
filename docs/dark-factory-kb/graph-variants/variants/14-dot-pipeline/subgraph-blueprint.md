# Subgraph: blueprint

**Theme:** załaduj i zwaliduj `blueprint.dot` — graf jest kodem.  
**Mode mix:** 100% DET. Zero LLM.

## Flow

```mermaid
flowchart TD
  A([enter Mdiamond]) --> B[DET: locate blueprint.dot]
  B --> C[DET: parse_dot]
  C --> D{schema + shapes OK?}
  D -->|no| E[DET: validate fail — exit]
  E --> Z([leave: idle / config error])
  D -->|yes| F[DET: bind klepacz stage ids]
  F --> G[DET: build walk plan + checkpoints]
  G --> H[DET: ensure no agent-routing edges]
  H --> I([leave: validated walk plan])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class B,C,F,G,H,E det
```

## Notes

- **Graph-is-code.** Zmiana procesu = edycja DOT, nie prompt „zrób inaczej dziś”.
- **Validate bez API key.** Jak samueljklee/attractor: zły shape / brak start-exit / nieznany tool = fail przed pierwszym boxem.
- **Shape allowlist.** Tylko Mdiamond, Msquare, box, parallelogram, diamond, hexagon. Inne → reject.
- **Bind do klepacza.** Stage ids mapują się na atomy: `pick_one_labeled`, `worktree_add`, `plan_issue`, `implement`, `run_tests`, `open_pr`, `pr_review`, `merge_policy` — nie research/SSG theatre.
- **Handoff contract.** Output = `{dot_ast, walk_plan, stage_bind, checkpoint_store}` dla det-walk.
