# Subgraph: draft-pr

**Theme:** harness **commit + push + `gh pr create --draft`**; coder ceiling; **nigdy merge**.  
**Mode mix:** 100% DET. Zero AGENT.

## Flow

```mermaid
flowchart TD
  A([enter: from impl-tests — worktree + test receipt]) --> B[DET: stage + commit on agent/issue-N]
  B --> C[DET: git push origin harness credentials]
  C --> D[DET: gh pr create --draft + Closes N]
  D --> E[DET: embed test pass/fail in PR body]
  E --> F[DET: release SQLite lease]
  F --> G([leave: PR draft — human review/merge])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef stop fill:#2a1a1a,stroke:#a05050,color:#ffe8e8
  class B,C,D,E,F det
  class G stop
```

## Notes

- **Harness-only git/GitHub write.** Claude nigdy nie woła `git push` ani `gh pr create`.
- **Draft only.** `--draft`; `MergePolicy` default Off. Człowiek merguje.
- **Closes N.** Body wiąże PR z issue; test receipt w opisie.
- **Lease release.** Po otwarciu PR (lub hard fail) SQLite lease wraca — następne `agent-ready` może wejść.
- **Escape.** Push/API fail → receipt + lease release + opcjonalny re-label HITL; nie auto-retry bez capu.
- **Handoff contract.** `{pr_url, draft: true, test_status, lease: released}` — terminal dla automatu.
