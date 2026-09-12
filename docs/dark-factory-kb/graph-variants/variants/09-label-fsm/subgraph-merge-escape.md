# Subgraph: merge-escape

**Theme:** merge Off|Classify|Always + obowiązkowy escape `needs-human`; supervisor cron.  
**Mode mix:** 100% DET policy. Agent nie merguje.

## Flow

```mermaid
flowchart TD
  A([enter: pr-open / escape signal / cron]) --> B{entry?}
  B -->|needs-human signal| H[DET: label → workflow:needs-human]
  H --> P[DET: HITL ping once]
  P --> Z0([leave: human owns])
  B -->|supervisor stranded| C{nudges ≥ 2?}
  C -->|yes| H
  C -->|no| D[DET: re-drive last legal stage]
  D --> Z1([leave: re-drive])
  B -->|stage pr-open| E[DET: read MergePolicy knobs]
  E --> F{policy}
  F -->|Off| G[DET: leave PR open + ping]
  G --> Z2([leave: hold human merge])
  F -->|Always| I{CI green + gates?}
  I -->|no| H
  I -->|yes| J[DET: merge + label done]
  J --> Z3([leave: done])
  F -->|Classify| K{low risk paths/size?}
  K -->|low + CI| J
  K -->|high / unknown| G

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  classDef ok fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class B,C,D,E,G,H,I,J,K,P det
  class Z0 bad
  class Z3 ok
```

## Notes

- **merge_gate ≠ persona.** gp-foundry: policy YAML (CI, size, paths). Tu to samo — Classify to reguły, nie prompt „czy wygląda OK”.
- **Default Off.** chippingway / jnurre: człowiek merguje; klepacz kończy na gotowym PR + jednym pingu HITL.
- **Escape first-class.** Każda ścieżka fail/cap/strand kończy w `workflow:needs-human`. Brak escape w grafie = nielegalna kompozycja.
- **Supervisor cron.** Re-drive raz/dwa; potem human. Bez nieskończonego „nudge w pętli”.
- **done = terminal.** Po merge: cleanup worktree, zdejmij stage, ustaw `workflow:done` (opc. jnurre post-merge cleanup).
- **Handoff:** `{merged|hold|needs_human, pr_url}`.
