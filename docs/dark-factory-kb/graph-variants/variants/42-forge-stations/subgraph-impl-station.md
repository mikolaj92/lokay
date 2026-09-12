# Subgraph: impl-station

**Theme:** stacja `impl` — implementacja w efemerycznym Podman + open PR.  
**Mode mix:** DET sandbox lifecycle + AGENT SO `implement_in_station`. Sufit = open PR; zero merge.

## Flow

```mermaid
flowchart TD
  A([enter: station=impl + approved plan]) --> B[DET: spawn Podman per repo]
  B --> C{sandbox ok?}
  C -->|fail| ESC([leave: escalate sandbox])
  C -->|ready| D[DET: checkout branch ai/issue-N]
  D --> E[AGENT SO: implement_in_station]
  E --> F{ok?}
  F -->|false| SKIP([leave: skip / cannot_implement])
  F -->|true| G[DET: apply diffs + local smoke]
  G --> H{smoke ok?}
  H -->|no + budget| E
  H -->|no exhausted| ESC
  H -->|yes| I[DET: commit / push / open PR]
  I --> J([leave: station→ci + pr_url])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  classDef stop fill:#2a1a1a,stroke:#a05050,color:#ffe8e8
  class B,D,G,I det
  class E agent
  class ESC,SKIP stop
```

## Notes

- **Podman ephemeral.** Scoped repo mount, non-root, sieć wg polityki forge. Po stacji kontener pada; stan żyje w gicie + journal.
- **Agent bez routingu.** SO dostaje plan tasks + wycinek plików; zwraca structured diffs. Nie woła „open PR” ani „goto ci” — to DET po smoke.
- **Jeden ticket, jeden PR (K=1).** Cross-repo = sekwencja sandboxów w tej samej stacji, jeden logical PR set / linked PRs — nie równoległy chaos occupancy.
- **Coder ceiling.** `open_pr` kończy stację `impl`. Merge = później, human, inna stacja.
- **Handoff.** `{pr_urls[], branch, commits[], smoke_ok:true}` → ci-review-station.

## Structured output — `implement_in_station`

```json
{
  "ok": true,
  "diffs": [
    {"repo": "org/app", "path": "src/api.py", "patch": "--- a/...\\n+++ b/..."}
  ],
  "notes": "implements task-1",
  "tests_touched": ["tests/test_api.py"]
}
```

```json
{ "ok": false, "reason": "cannot_implement|plan_gap|sandbox_limit|dangerous" }
```
