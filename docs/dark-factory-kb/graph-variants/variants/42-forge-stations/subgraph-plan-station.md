# Subgraph: plan-station

**Theme:** stacja `plan` — artefakty PRD/epic/tasks + human approve.  
**Mode mix:** AGENT SO `plan_artifacts` + HITL gate. Agent nie przechodzi sam do `impl`.

## Flow

```mermaid
flowchart TD
  A([enter: station=plan]) --> B[DET: pack ticket + repo map]
  B --> C[AGENT SO: plan_artifacts]
  C --> D{ok?}
  D -->|false| SKIP([leave: skip / underspecified])
  D -->|true| E[DET: persist plan PR / artifacts]
  E --> F{HITL: human approve plan?}
  F -->|reject + notes| C
  F -->|approve| G([leave: station→impl])
  F -->|timeout / hold| HOLD([leave: hold for human])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  classDef hitl fill:#2a1a3a,stroke:#8a5ab8,color:#f3e8ff
  class B,E det
  class C agent
  class F hitl
```

## Notes

- **Cross-repo OK.** Forge SDLC planuje po wielu repo; SO zwraca `repos[]` + tasks per repo. Impl potem spawnuje Podman per repo.
- **HITL jest krawędzią.** Approve = DET advance `plan→impl`. Reject wraca do tego samego slotu z notes — nie „agent zdecydował iść dalej”.
- **Artefakty, nie czat.** PRD / epic / task list to wersjonowane pliki (np. plan PR), nie ulotny thread.
- **Fail closed.** `ok:false` (underspecified / too_large / dangerous) → skip/hold; spine nie wchodzi w `impl`.
- **Handoff.** `{plan_id, repos[], tasks[], acceptance[], approved_by}` → impl-station.

## Structured output — `plan_artifacts`

```json
{
  "ok": true,
  "summary": "short epic intent",
  "repos": ["org/app", "org/lib"],
  "tasks": [
    {"repo": "org/app", "title": "add endpoint", "files_hint": ["src/api.py"]}
  ],
  "acceptance": ["CI green", "endpoint returns 200"],
  "risks": ["migration"],
  "confidence": "high"
}
```

```json
{ "ok": false, "reason": "underspecified|too_large|dangerous|cross_repo_unclear" }
```
