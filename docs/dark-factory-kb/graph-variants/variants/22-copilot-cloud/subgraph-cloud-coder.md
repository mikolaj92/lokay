# Subgraph: cloud-coder

**Theme:** Copilot / headless agent jako **liść** na ephemeral host — implement (+ opc. thin plan); meat ≡ AI.  
**Mode mix:** AGENT SO tylko w liściach; test/commit lokalne na VM = DET.  
**Handoff in:** cell ready on VM.  
**Handoff out:** `{branch, commit_shas, summary}` → draft-pr-ceiling, albo `{skip|fail, reason}` → tear-down.

## Flow

```mermaid
flowchart TD
  A([enter: cell ready on VM]) --> B{thin plan?}
  B -->|optional| P[AGENT SO: plan_issue]
  P -->|ok:false underspecified / dangerous| S([leave: skip — tear-down upstream])
  P -->|ok| C[AGENT SO: implement on this host only]
  B -->|skip plan| C
  C -->|ok:false| S2([leave: fail / needs_split])
  C -->|ok| D[DET: assert still single host / no mid-flight seed]
  D -->|second host / catalog seed| V([leave: fail K=1])
  D -->|ok| E[DET: run verification from issue]
  E -->|red, attempts < N| R[AGENT SO: repair_code bounded]
  R --> E
  E -->|red, budget out| S2
  E -->|green| F[DET: stage + commit on ai/issue-N]
  F --> G[DET: push origin]
  G -->|fail| X([leave: fail git])
  G -->|ok| Y([leave: branch pushed — ready for draft PR])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  classDef stop fill:#2a1a1a,stroke:#a05050,color:#ffe8e8
  classDef ok fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class D,E,F,G det
  class P,C,R agent
  class S,S2,V,X stop
  class Y ok
```

## AGENT leaves (structured output)

| Leaf | Schema (ok) | Schema (fail) |
|------|-------------|-----------------|
| `plan_issue` *(opc.)* | `{ok, goal, files, test_command, non_goals, stop_if}` | `{ok:false, reason: underspecified\|too_large\|dangerous}` |
| `implement` | `{ok, summary, files_touched, tests_run}` | `{ok:false, reason: cant_comply\|needs_split\|blocked_path}` |
| `repair_code` | same as implement | budget / same fail enums |

## Notes

- **Reuse fidelity.** Copilot coding agent siedzi na ephemeral VM i klepie diff; ready-for-agent: headless leaf w worktree. Tu liść **kończy na pushed branch** — open draft PR to osobny DET ceiling.
- **Liść, nie orkiestrator.** Agent dostaje SO schema; nie routuje factory_pass, nie pickuje sąsiada, nie merguje.
- **Głupi i posłuszny.** Trzymaj się issue: In scope / Out / Ask-or-stop (auth, billing, migracje, deps). Inteligentny „ulepszacz” = ryzyko (KLEPACZ).
- **Bounded repair.** max N na `repair_code`; potem skip + evidence — nie wieczne limbo na płatnym hoście.
- **No mid-flight seed.** Zakaz drugiego hosta / drugiego ticketa / „przy okazji #N+1”.
- **Coder ceiling jeszcze nie tu.** Merge i nawet open-PR żyją w `draft-pr-ceiling` — ten subgraph tylko pushuje branch.
