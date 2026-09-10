# Google Jules

**Confidence: 84** — async session → plan (±approve) → GCP VM → AUTO_CREATE_PR; klepacz z jawnym stanem sesji, nie L5.

## Co to jest

Async coding agent Google Labs/Cloud: trigger (UI/CLI/API/GH label|mention) → Session w puli → PLANNING → exec na ephemeral VM + Environment Snapshot → opcjonalnie PullRequest. Merge zostaje u człowieka.

## Graf

```mermaid
flowchart TD
  trig[jules.google / CLI / API / GH label|mention] --> q[Session QUEUED]
  q --> plan[PLANNING]
  plan --> appr{requirePlanApproval?}
  appr -->|tak| await[AWAITING_PLAN_APPROVAL]
  await --> prog[IN_PROGRESS]
  appr -->|nie| prog
  prog --> vm[Ephemeral GCP VM + snapshot deps]
  vm --> work[Clone → edit → bash/tests → artifacts]
  work --> mode{automationMode}
  mode -->|AUTO_CREATE_PR| pr[SessionOutput.PullRequest]
  mode -->|inne| patch[GitPatch / ChangeSet]
  pr --> human[Human review + merge]
  patch --> human
  work --> fail[FAILED / PAUSED / feedback]
```

## Co / gdzie / jak

| Element | Wartość |
|---------|---------|
| Trigger | Web UI, CLI, REST API, GitHub label/mention |
| Sandbox | Ephemeral Google Cloud VM; Environment Snapshot |
| Stany | QUEUED → PLANNING → AWAITING_PLAN_APPROVAL? → IN_PROGRESS → COMPLETED/FAILED/PAUSED |
| Gates | `requirePlanApproval`; steerability planu; AWAITING_USER_FEEDBACK |
| PR | `automationMode=AUTO_CREATE_PR` — tworzy PR, nie merguje |
| Eval | BashOutput z exitCode w Activity; potem standardowe GH CI |
| Parallelizm | Wiele Session = wiele VM; nie shared Missions-orchestrator |
| Model | Gemini lineage (Pro plan / Flash steps — reporty); GA ~2025-08 |
| Nie robi | Auto-merge/deploy; gwarantowany multi-day checkpoint jak Devin workflows |

## Linki

- https://jules.google/
- https://jules.google/docs/api/reference/types/
- https://blog.google/innovation-and-ai/models-and-research/google-labs/jules/
