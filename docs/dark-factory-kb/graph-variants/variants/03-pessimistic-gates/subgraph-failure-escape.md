# Subgraph: failure-escape

**Theme:** sklasyfikuj fail → receipt → stop albo HITL. **Żadnych limbo labels.**  
**Mode mix:** DET classify + write receipt; HITL tylko gdy `needs_human`. Escape hatch całego wariantu.

## Flow

```mermaid
flowchart TD
  A([enter: blocked / fail + reason]) --> B[DET: normalize reason enum]
  B --> C{reason class}
  C -->|dirty_worktree / missing_label / underspecified| D[DET: write receipt + stop]
  C -->|stuck_pr / ci_timeout / ci_red| E[DET: annotate PR/issue with receipt]
  E --> F{auto-requeue allowed?}
  F -->|no — default| D
  F -->|yes + budget| Q([leave: requeue signal — top may retry later])
  C -->|local_test_red / push_fail / pr_open_fail| D
  C -->|review_reject / merge_blocked / high_risk| G[HITL: human hold]
  G --> H[DET: left_open receipt — no limbo label]
  H --> I([leave: stop — human owns])
  D --> J([leave: stop — clean fail])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef human fill:#2a1a3a,stroke:#8a5ab8,color:#f3e8ff
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  class B,D,E,F,H det
  class G human
  class J,I bad
```

## Reason enum (closed)

| reason | Default exit | Limbo label? |
|--------|--------------|--------------|
| `dirty_worktree` | stop | **never** |
| `missing_label` | stop | **never** |
| `underspecified` | stop | **never** |
| `stuck_pr` | stop / optional requeue | **never** |
| `ci_timeout` | stop | **never** |
| `ci_red` | stop | **never** |
| `local_test_red` | stop | **never** |
| `push_fail` / `pr_open_fail` | stop | **never** |
| `review_reject` | HITL hold | **never** |
| `merge_blocked` | HITL hold | **never** |
| `high_risk` | HITL hold | **never** |

## Notes

- **Escape ≠ limbo.** Limbo label to odkładanie wstydu. Tu: receipt JSON + stop albo jawny human hold.
- **Receipt jest skutkiem.** `{reason, issue_id?, pr_url?, checks?, ts, next: stop|human|requeue}` — audytowalny, nie etykieta na tablicy.
- **Requeue rzadki.** Tylko gdy policy + budget na `stuck_pr` / CI flake class; default = stop. Pessimista nie zapętla w nieskończoność.
- **HITL nie jest LLM.** High-risk / reject / merge_blocked → człowiek (architektura / QA). Graf nie udaje decyzji.
- **Top-level łączy tu wszystkie `blocked` / `fail`.** Bez tego podgrafu monolit gubi fail paths.
- **Handoff:** `{stopped:true, receipt}` | `{human_hold:true, receipt}` | `{requeue:true, receipt}` — nigdy `{label: limbo}`.
