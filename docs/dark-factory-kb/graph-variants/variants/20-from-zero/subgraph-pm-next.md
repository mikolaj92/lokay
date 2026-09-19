# Subgraph: pm-next

**Theme:** wejście do PM → odczytanie następnej roboty.  
**Mode mix:** prawie wyłącznie DET; zero kodowania.

## Flow

```mermaid
flowchart TD
  A([enter subgraph]) --> B[DET: authenticate / enter PM]
  B --> C{PM reachable?}
  C -->|no| X[DET: stop — fail closed]
  X --> Z0([leave: blocked])
  C -->|yes| D[DET: list / fetch next job]
  D --> E{job available?}
  E -->|no| F[DET: idle / exit clean]
  F --> Z1([leave: idle])
  E -->|yes| G[DET: pick next actionable job]
  G --> H([leave: job ref ready])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class B,D,G,F,X det
```

## Notes

- **Blank-slate front door.** Only: enter the project-management place, then read the next job. No mill names, no triage theatre.
- **Optimistic clarity.** If there is no job, leave idle — do not invent work.
- **Fail closed on PM.** Auth / reachability failures stop the chain; no AGENT recovery that hides broken plumbing.
- **Handoff contract.** Output = `{pm_context, job_ref}` for ticket subgraph.
