# Subgraph: worktree-plan

**Theme:** świeży **git worktree** + liść **Plan** + HITL `implement`; harness flipuje `agent-planned`.  
**Mode mix:** DET sandbox/labels + AGENT PlanAgent + HITL gate.

## Flow

```mermaid
flowchart TD
  A([enter: from label-lease — claimed]) --> B[DET: fresh git worktree agent/issue-N]
  B --> C[DET: load issue body + context into worktree]
  C --> D[AGENT: PlanAgent — claude -p plan mode]
  D --> E{plan non-empty + actionable?}
  E -->|no| F[DET: receipt plan_reject]
  F --> Z0([leave: release / escape])
  E -->|yes| G[DET: post plan as issue comment]
  G --> H[DET: add label agent-planned]
  H --> I{HITL: human reply}
  I -->|tekst ≠ implement| J[DET: keep planned / rewind]
  J --> D
  I -->|implement| K([leave: handoff impl-tests])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef ag fill:#2a1a3a,stroke:#8a5ab8,color:#f3e8ff
  classDef hitl fill:#3a2a1a,stroke:#b88a3a,color:#fff8e8
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  class B,C,G,H,J det
  class D ag
  class I hitl
  class F,Z0 bad
```

## Notes

- **Harness owns worktree.** `git worktree add`; agent bez `git push` / `gh pr`.
- **LLM only plan.** `claude -p --output-format stream-json` — structured plan, nie orkiestracja FSM.
- **HITL gate.** Reply dokładnie `implement` → dalej; inaczej rewizja planu (AbleInc kanon).
- **Label `agent-planned`.** Tylko harness dokleja po komentarzu planu.
- **Meat ≡ AI.** Człowiek-klepacz może wkleić ten sam plan-komentarz bez zmiany krawędzi.
- **Handoff contract.** `{worktree, branch, plan_comment_id, label: agent-planned}` albo `{fail: plan_reject}`.
