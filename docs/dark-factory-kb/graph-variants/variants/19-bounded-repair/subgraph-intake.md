# Subgraph: intake

**Theme:** pick labeled → worktree/branch → pierwsze `implement`. Wejście do łańcucha bounded repair.  
**Mode mix:** DET front door; jeden AGENT SO `implement`. Zero repair tutaj — to robi `repair-code`.

## Flow

```mermaid
flowchart TD
  A([enter: cron / start]) --> B[DET: list ready-for-agent / ai:ready]
  B --> C{any?}
  C -->|none| X([leave: none → skip-escape idle])
  C -->|yes| D[DET: pick one K=1 + claim]
  D --> E{underspecified? no acceptance}
  E -->|yes| X2([leave: blocked underspecified → skip-escape])
  E -->|no| F[DET: worktree / branch ai/issue-N]
  F --> G{dirty / conflict?}
  G -->|yes| X3([leave: blocked dirty → skip-escape])
  G -->|clean| H[AGENT SO: implement ticket]
  H --> I{ok + files changed?}
  I -->|ok:false / empty| X4([leave: fail implement → skip-escape])
  I -->|ok| J([leave: issue + branch + draft diff → repair-code])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  class B,D,E,F,G det
  class H agent
  class X,X2,X3,X4 bad
```

## Notes

- **K=1 occupancy.** Jeden ticket naraz. Occupancy DET; agent nie „bierze z czatu”.
- **Ticket jasny albo skip.** Brak acceptance / verification → `underspecified` → skip-escape. Nie planuj aż będzie sens (to wariant 19, nie planner).
- **Dirty = blocked.** Pessimista nie zaczyna na brudnym drzewie; receipt, nie limbo.
- **Implement ≠ repair.** Pierwszy SO tylko kładzie draft. Lokalny test i `repair_code` są w następnym podgrafie — żeby licznik N był jawny.
- **Handoff.** `{issue_id, branch, worktree, draft_summary, files[], repair_code_used:0}` albo `{blocked|none, reason}` → skip-escape.

## Structured output — `implement`

```json
{
  "ok": true,
  "summary": "add null guard in Foo.bar",
  "files": ["src/foo.py", "tests/test_foo.py"]
}
```

```json
{ "ok": false, "reason": "cant_comply|needs_split|blocked_path|empty" }
```
