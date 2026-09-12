# Subgraph: script-hitl

**Theme:** `script` / `set` / `mcp` / `human_gate` / `terminate` — plumbing i HITL bez modelu.  
**Mode mix:** DET + HITL. Zero tokenów na git/test/PR/merge policy.

## Flow

```mermaid
flowchart TD
  A([enter: script-hitl step]) --> B{kind?}
  B -->|set| S[DET: bind vars ticket attempt policy]
  B -->|script| T[DET: shell pytest gh git worktree]
  B -->|mcp no-LLM| M[DET: tool call without model]
  B -->|human_gate| H{{HITL: approve / deny / clarify}}
  B -->|terminate| Z[DET: end success or failed]
  S --> OUT([leave: resume jinja-routes])
  T --> C{exit code?}
  C -->|0| OK[DET: set tests_ok / pr_url]
  C -->|nonzero| FAIL[DET: set failure_log attempt++]
  OK --> OUT
  FAIL --> OUT
  M --> OUT
  H -->|approve / Always| MER[DET: merge_policy exec]
  H -->|deny / changes| BACK([leave: vars for agent-leaf])
  H -->|Off hold| WAIT([leave: wait human])
  MER --> Z
  Z --> DONE([leave: done Msquare])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef hitl fill:#2a2a1a,stroke:#b8a03a,color:#fffce8
  class S,T,M,OK,FAIL,MER,Z det
  class H hitl
```

## Notes

- **Script owns side effects.** pick_one_labeled, worktree, pytest, commit, push, `gh pr create` — `script`, nie agent z otwartym shelem-orkiestatorem.
- **Merge policy Off|Classify|Always** egzekwowane tu (DET + opcjonalny `human_gate`), nie werdyktem LLM jako jedyną bramką.
- **Bounded repair.** `attempt++` + Jinja `attempt < N` wraca do `type: agent` fix; wyczerpanie → `terminate failed` / escalate — nie „napraw świat”.
- **HITL = gate, nie chat-loop.** Conductor `human_gate` / dialog clarify; człowiek nie trzyma orkiestracji w RAM modelu.
- **Handoff contract.** Leave routes = zaktualizowane `vars`; leave done = `{status, pr_url?, reason?}`.
