# Subgraph: loop-gate

**Theme:** DET predicate na wyniku ticka — **continue / LOOP_COMPLETE / arch HITL / skip**.  
**Mode mix:** DET bramka + HUMAN przy architekturze. Zero LLM w orkiestracji.

## Flow

```mermaid
flowchart TD
  A([enter: tick result]) --> B{review.loop_status?}
  B -->|reject| S([leave: skip receipt reject])
  B -->|needs_arch_human| H[HUMAN: architecture decision]
  H -->|redesign / stop| S2([leave: skip or human stop])
  H -->|approved — continue loop| C
  B -->|continue| C{ralph_tick_used < soft_max?}
  C -->|yes| L([leave: continue → ralph-tick])
  C -->|no soft_max| H2[HUMAN or skip: soft_max exhausted]
  H2 -->|human extends budget explicitly| L
  H2 -->|no| S3([leave: skip soft_max_exhausted])
  B -->|LOOP_COMPLETE| D{arch_flags empty / already cleared?}
  D -->|no| H
  D -->|yes| E{test_green?}
  E -->|no| C
  E -->|yes| F([leave: LOOP_COMPLETE → git-pr])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef human fill:#2a1a3a,stroke:#8a5ab8,color:#f3e8ff
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  classDef ok fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class B,C,D,E det
  class H,H2 human
  class S,S2,S3 bad
  class L,F ok
```

## Notes

- **Bramka jest DET.** Mapowanie `loop_status` → krawędź grafu jest twarde; agent nie routuje „co dalej”.
- **`LOOP_COMPLETE` ≠ merge.** Complete tylko puszcza do `subgraph-git-pr.md`. Merge zostaje MergePolicy (Off domyślnie) — SOUL / not L5.
- **Soft max chroni przed Ralph forever.** Default 8 (MANIFEST). Przedłużenie budżetu = **jawny człowiek**, nie prompt „jeszcze trochę”.
- **Architecture = humans.** `needs_arch_human` albo niepuste `arch_flags` przy complete → HITL. Agent nie zatwierdza migracji / auth / public API sam.
- **Zielony test wymagany przy complete.** Jeśli review krzyczy COMPLETE na czerwono — wróć do continue (fail-closed), nie otwieraj PR.
- **Skip z receipt, nie limbo.** Powody: `reject`, `soft_max_exhausted`, `human_stop`. Zakazane: `ai:deferred`, `needs-human-maybe`, limbo theatre.
- **Handoff.** `{action: continue|git_pr|skip|human_wait, ralph_tick_used, reason?}`.
