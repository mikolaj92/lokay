# Subgraph: dot-spine

**Theme:** załaduj i zwaliduj `*.fabro` digraph — DOT jest kodem.  
**Mode mix:** 100% DET. Zero LLM.

## Flow

```mermaid
flowchart TD
  A([enter Mdiamond]) --> B[DET: locate ticket-to-pr.fabro]
  B --> C[DET: fabro parse digraph]
  C --> D{exactly one start + exit?}
  D -->|no| E[DET: validate fail — exit]
  E --> Z([leave: idle / config error])
  D -->|yes| F[DET: shape/type allowlist + handlers]
  F --> G{unknown handler / bad @file?}
  G -->|yes| E
  G -->|no| H[DET: bind klepacz stage ids]
  H --> I[DET: build run plan + sandbox env id]
  I --> J[DET: reject LLM-in-condition edges]
  J --> K([leave: validated digraph + env])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class B,C,F,H,I,J,E det
```

## Notes

- **Graph-is-code.** Zmiana procesu = edycja `.fabro`, nie prompt „zrób inaczej dziś”.
- **Validate bez API key.** Zły shape / brak start-exit / martwy `@prompts/…` / nieznany handler = fail przed pierwszym liściem.
- **Shape allowlist (klepacz).** Mdiamond, Msquare, box, tab, parallelogram, diamond, hexagon; opcjonalnie component/tripleoctagon. `house` manager_loop — zwykle **out** (nie department brain).
- **Bind do klepacza.** Stage ids → `pick_one_labeled`, `worktree_add`, `plan_issue`, `implement`, `run_tests`, `open_pr`, `pr_review`, `merge_policy` — nie research/SSG.
- **Sandbox env.** Run config wybiera `docker` | `local` | `daytona` **przed** pierwszym boxem — agenci nie wybierają hosta.
- **Handoff contract.** Output = `{dot_ast, stage_bind, sandbox_env, run_id}` dla engine-routes.
