# Subgraph: sandbox-build

**Theme:** **Hybrid free half** — Building = persistent coding agent w izolowanym sandboxie; freer niż DET atom leaf.  
**Mode mix:** DET provision/budget + AGENT free tools **inside** sandbox. Stage advance poza Building nadal u factory/HITL.

## Flow

```mermaid
flowchart TD
  A([enter: plan approved → Building]) --> B[DET: provision sandbox platform|local]
  B --> C[DET: bind work_item session + clone + install]
  C --> D[DET: inject plan_ref + repo checks command + budget]
  D --> E[AGENT free: multi-turn tools IN sandbox — edit/bash/test]
  E --> F{session outcome?}
  F -->|impl ready| G[DET: run repo checks / CI hook]
  F -->|need clarify mid-build| H[DET: pause → human comment / re-triage hint]
  F -->|budget / unsafe| NO[DET: fail closed + evidence comment]
  G -->|checks green| PR[DET: push branch + open PR → Review station]
  G -->|checks red| E2[AGENT free: bounded repair in same sandbox]
  E2 --> G
  E2 -->|repair budget exhausted| NO
  PR --> OUT([leave: review-complete])
  H --> WAIT([leave: wait human / triage-plan-gates])
  NO --> OUT2([leave: idle / escalate])
  B -->|provision fail| NO

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  classDef hybrid fill:#2a2a1a,stroke:#b8a03a,color:#fff8e8
  class B,C,D,G,PR,NO,H det
  class E,E2 hybrid
```

## Notes

- **Free ≠ router.** Agent swobodnie wybiera *jak* budować w sandboxie; **nie** wybiera następnego stage Factory (nie skipuje Review, nie merguje).
- **Dlaczego „hybrid” tu żyje.** ElasticClaw/Fabro = agent jako wąski leaf pod hubem. Mastra Building = dłuższa, persistent session — nadal za bramką planu, ale z większą autonomią narzędziową.
- **Providers.** Mastra platform sandboxes lub `FACTORY_SANDBOX_PROVIDER=local`. Jeden work item → jedna sesja/sandbox.
- **Budget DET wokół free.** Timeout / max turns / network policy — fail closed, nie „napraw świat”.
- **Coder ceiling.** Open PR + handoff do Review — build session **nie** klika Merge.
- **Meat ≡ AI.** Ten sam sandbox seat.
- **Handoff.** Leave = `{work_item_id, pr_url, branch, checks_ok, usage, sandbox_id}`.
