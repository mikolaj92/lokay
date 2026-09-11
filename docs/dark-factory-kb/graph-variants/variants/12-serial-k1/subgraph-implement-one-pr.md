# Subgraph: implement-one-pr

**Theme:** AGENT implement w **jednej** komórce → test DET → commit/push → **dokładnie jeden** PR.  
**Mode mix:** AGENT SO (implement, opc. thin plan) + DET git/PR.  
**Handoff in:** worktree ready (catalog sealed).  
**Handoff out:** `{ok:true, pr_url, branch, closes: N}` albo fail/skip receipt — **bez** siewu katalogu.

## Flow

```mermaid
flowchart TD
  A([enter: cell ready — catalog sealed]) --> B{thin plan?}
  B -->|optional| P[AGENT SO: plan_issue]
  P -->|ok:false underspecified| S([leave: skip receipt — unlock])
  P -->|ok| C[AGENT SO: implement in this worktree only]
  B -->|skip plan| C
  C -->|ok:false| S2([leave: fail / needs_split — unlock])
  C -->|ok| D[DET: assert still single worktree]
  D -->|second path / seed attempt| V([leave: fail K=1 / mid-flight seed])
  D -->|ok| E[DET: local test gate]
  E -->|red| R{bounded repair ≤1?}
  R -->|yes same leaf| C
  R -->|no| S2
  E -->|green| F[DET: commit on issue branch]
  F --> G[DET: push origin]
  G --> H[DET: assert_no_open_pr_yet]
  H -->|PR already exists| V2([leave: fail second PR])
  H -->|none| I[DET: open exactly one PR Closes N]
  I -->|fail| X([leave: fail git/pr])
  I -->|ok| J[DET: assert pr_count == 1 for ticket]
  J -->|≠1| V2
  J -->|1| Y([leave: one PR open — still no catalog seed])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  classDef stop fill:#2a1a1a,stroke:#a05050,color:#ffe8e8
  classDef ok fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class D,E,F,G,H,I,J det
  class P,C agent
  class S,S2,V,V2,X stop
  class Y ok
```

## AGENT leaves (structured output)

| Leaf | Schema (ok) | Schema (fail) |
|------|-------------|-----------------|
| `plan_issue` *(opc.)* | `{ok, goal, files, test_command, non_goals, stop_if}` | `{ok:false, reason: underspecified\|too_large\|dangerous}` |
| `implement` | `{ok, summary, files_touched, tests_run}` | `{ok:false, reason: cant_comply\|needs_split\|blocked_path}` |

## DET atoms (git / K=1 guards)

| Atom | ok means | fail |
|------|----------|------|
| `assert_single_worktree` | path count = 1 dla misji | `k1_violation` |
| `forbid_catalog_seed` | brak nowych ticket entries w runtime catalog | `mid_flight_seed` |
| `local_test` | test_command exit 0 | `test_red` |
| `commit_issue_branch` | commit na `ai/issue-N-…` | `git_failed` |
| `push_origin` | remote updated | `push_failed` |
| `assert_no_open_pr_yet` | 0 open PR dla issue | `pr_already_open` |
| `open_pr_closes_n` | dokładnie 1 PR, body `Closes #N` | `pr_failed` |
| `assert_pr_count_one` | count(open+just_created)=1 | `k1_pr_violation` |

## Notes

- **No catalog seeding mid-flight.** Między enter a leave executor **nie** woła pick/list do dorzucenia sąsiada, **nie** `worktree add` drugiego path, **nie** otwiera drugiego PR. Guardy DET to egzekwują.
- **Jedna komórka.** Implement czyta tylko cell context (issue + allow_paths). Zakaz „przy okazji zrób #N+1”.
- **Jedna szansa repair lokalnie.** Test czerwony → max 1 bounded retry w tym samym liściu **albo** fail + unlock. Nie zagnieżdżony SDLC i nie nowy worktree.
- **Coder ceiling = open PR.** Merge nie żyje tutaj.
- **Meat ≡ AI.** Ten sam kontrakt SO niezależnie kto siedzi w liściu.
