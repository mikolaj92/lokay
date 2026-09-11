# Subgraph: gha-dispatch

**Theme:** stały YAML GHA na `issues.labeled` = deterministyczny dispatch; concurrency per issue; flip `in-progress`.  
**Mode mix:** 100% DET. Claude jest *wywoływany później*, nie orkiestruje jobów.

## Flow

```mermaid
flowchart TD
  A([enter: matched start label]) --> B[DET: job if-guard label == auto-fix|agentic-fix]
  B --> C[DET: concurrency group issue-N cancel-in-progress false]
  C --> D[DET: permissions least privilege]
  D --> E[DET: flip label → in-progress]
  E --> F{occupancy: live run / branch?}
  F -->|conflict| G[DET: comment defer + keep or failed]
  G --> Z0([leave: defer])
  F -->|free| H[DET: checkout + wire ANTHROPIC_API_KEY]
  H --> I[DET: set timeout ~30m + env from template]
  I --> J([yield: worktree])
  J -->|cell ready| K([leave: ready for claude-leaf])
  J -->|cell fail| L[DET: label *-failed]
  L --> Z1([leave: fail receipt])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  class B,C,D,E,F,G,H,I,L det
  class Z0,Z1 bad
```

## Fixed step table (compose)

| # | Step | Who | Notes |
|---|------|-----|-------|
| 1 | `on: issues.labeled` | DET | jedyny impuls start |
| 2 | `if: label == auto-fix \| agentic-fix` | DET | fail closed |
| 3 | `concurrency: issue-N` | DET | Solvio: per-issue; no double fix |
| 4 | flip `in-progress` | DET | FSM advance — not agent |
| 5 | permissions + secrets wire | DET | never in prompt body |
| 6 | timeout / env template | DET | ~30m Solvio-style |
| 7 | yield worktree subgraph | DET | next cell |

## Notes

- **YAML is the program.** Kolejność stała jak w Claude Action / Codex harness — model nie dopisuje `steps:`.
- **Self-hosted OK.** JP często self-hosted ($0 Actions minutes); hosted też działa — graf bez zmian.
- **JBS phases.** Prepare/Fix/Verify/Submit = te same DET kroki rozpisane nazwami; nadal jeden dispatch spine.
- **Prompt/env = template.** Issue body + `CLAUDE.md` / issue template (repro/expected) wypełniają kontekst; nie „zdecyduj co w fabryce”.
- **Handoff.** `{issue_id, family, runner, secrets_ready, stage: in-progress}` → worktree.
