# Subgraph: ephemeral-host

**Theme:** spin-up świeżej maszyny chmurowej → clone tip → install — odpowiednik fresh worktree, poza lokalnym dyskiem.  
**Mode mix:** 100% DET.  
**Handoff in:** claimed issue payload.  
**Handoff out:** `{host_id, workdir, base_sha, branch}` albo `{fail, reason}` + zawsze tear-down path.

## Flow

```mermaid
flowchart TD
  A([enter: issue claimed]) --> B[DET: assert occupancy free]
  B -->|live| D([leave: defer — no second host])
  B -->|free| C[DET: spin_up ephemeral host]
  C -->|fail| X([leave: fail provision])
  C -->|ok| E[DET: clone base_ref @ tip]
  E --> F[DET: create issue branch ai/issue-N-…]
  F --> G[DET: install deps in cell]
  G -->|fail| T1[DET: tear-down host]
  T1 --> X2([leave: fail install])
  G -->|ok| H[DET: mark occupancy live]
  H --> Y([leave: cell ready on VM])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef stop fill:#2a1a1a,stroke:#a05050,color:#ffe8e8
  classDef ok fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class B,C,E,F,G,H,T1 det
  class D,X,X2 stop
  class Y ok
```

## DET atoms

| Atom | ok means | fail |
|------|----------|------|
| `assert_occupancy_free` | 0 live ephemeral missions | `defer` / `k1_violation` |
| `spin_up_host` | VM/session id + SSH/API handle | `provision_failed` |
| `clone_tip` | clean workdir @ `base_sha` | `clone_failed` |
| `branch_ai_issue` | `ai/issue-N-…` from tip | `git_failed` |
| `install_deps` | lockfile install exit 0 | `install_failed` |
| `mark_live` | occupancy = live | — |
| `tear_down_host` | VM gone; no dirty residue | best-effort; always attempted on fail path |

## Notes

- **Reuse fidelity.** ready-for-agent: fresh worktree + install. Copilot cloud: ephemeral runner. Tu ten sam kontrakt komórki — **jeden host na ticket**, zero shared dirty tree.
- **K=1 occupancy.** Drugi spin-up mid-flight = fail closed / defer. Serial, nie parallel fan-out.
- **Tear-down contract.** Każda ścieżka fail **oraz** happy path po draft PR (top-level) woła `tear_down_host`. Persistence = tylko remote branch + draft PR.
- **Brak lokalnego worktree.** Box użytkownika nie jest sandboxem; cloud cell jest efemeryczna.
- **Meat ≡ AI.** Ten sam DET spine niezależnie kto później siedzi w liściu AGENT.
