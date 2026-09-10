<!-- spine: spine_deterministic -->
# addyosmani/factory

**Repo:** [addyosmani/factory](https://github.com/addyosmani/factory) · ★179 · Shell / Claude Code + Codex skills · MIT

## Co to jest

Reference software factory **bez** własnego orchestratora: GitHub Issues + `factory:*` labels + Claude Code cloud routines (lub Codex) + `CHARTER.md` + `gates.sh` + fresh verifier. Issue → triage → ready-to-implement → draft PR → human merge. Autor: Addy Osmani (wysoka widoczność osoby; sam loop jest wzorcowy klepacz).

## Graf

```mermaid
flowchart LR
  I[GitHub issue] --> T[Scheduled triage]
  T -->|small + allowed| R[factory:ready-to-implement]
  T -->|needs decisions| S[factory:ready-to-spec]
  T -->|unclear| P[needs-info]
  S --> H[Human-guided spec gates]
  H --> R
  R --> B[Implementation run — claim branch]
  B --> G[gates.sh + fresh verifier]
  G --> D[Draft PR]
  D --> V[PR verification routine]
  V --> C["/factory control room"]
  C --> M{Human merge}
```

## Co / gdzie / jak

| Warstwa | Mechanizm |
|---------|-----------|
| **Trigger** | Schedule / GH events / optional API-trigger Action |
| **Stan** | Labels + `factory-handoff:v1` comment — sessionless |
| **Role** | Triage / implement / verify — każda run świeża |
| **Sandbox** | Claude Code / Codex session; charter limituje scope |
| **Testy** | Deterministic gates fail-closed gdy check missing |
| **Merge** | **Nigdy** agent — tylko człowiek |
| **Anti-race** | Deterministic branch `claude/fq-N`; first push wins |

Podręcznikowy KLEPACZ: charter = risk budget, label = weź, draft PR = output.

## Confidence

**80 / 100** — klarowny model operacyjny; nie obscure (brand autora); zależy od Claude routines jako clock.

## Linki

- https://github.com/addyosmani/factory
