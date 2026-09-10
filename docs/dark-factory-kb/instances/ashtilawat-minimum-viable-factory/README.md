# ashtilawat/minimum-viable-factory

**Repo:** [ashtilawat/minimum-viable-factory](https://github.com/ashtilawat/minimum-viable-factory) · ★40 · Python · LangGraph + Claude Code

## Co to jest

„Ticket in, deployed web app out” — Linear webhook → LangGraph → 6 agentów Claude Code w Docker (PM→Arch→Dev×N→Review∥Test→Deploy) z **trzema human gates** (In Spec / In Arch / In Dev→Deploy). Greenfield Next.js scaffold per ticket; brownfield „next”. Mission Control + memory/*.md.

## Graf

```mermaid
flowchart TD
  L[Linear ticket → In Spec] --> WH[Webhook → orchestrator]
  WH --> Prov[GitHub repo + Vercel + Supabase scaffold]
  Prov --> PM[PM Agent → spec memory]
  PM --> G1{GATE: move In Arch}
  G1 --> Arch[Architect → plan + subtasks]
  Arch --> G2{GATE: move In Dev}
  G2 --> Dev[N × Dev agents sequential same branch]
  Dev --> PR[Single PR]
  PR --> RT[Review ∥ Test parallel]
  RT --> G3{GATE: move In Deploy}
  G3 --> Dep[Deploy Agent → Vercel]
  Dep --> Done[Done + URLs]
```

## Co / gdzie / jak

| Warstwa | Mechanizm |
|---------|-----------|
| **Trigger** | Linear status / webhook signature verify |
| **Stan** | LangGraph + append-only `memory/` per ticket; Linear sub-issues |
| **Role** | 6 skills; zero agent-to-agent chat — tylko memory file |
| **Sandbox** | Docker + Claude Agent SDK; 5 MCP (Linear, GH, Vercel, Supabase, Slack) |
| **Testy** | Test Agent + Jest scaffold |
| **Merge/Deploy** | Human gate przed deploy; PR otwierany przed review |

**Uwaga klepacz:** to raczej **greenfield factory** (nowe repo per ticket) niż brownfield bugfix w istniejącym monorepo. Kształt ticket→PR jest, blast radius inny.

## Confidence

**58 / 100** — czytelne ~700 LOC, jasne bramki; greenfield bias + wiele SaaS keys; brownfield zapowiedziany.

## Linki

- https://github.com/ashtilawat/minimum-viable-factory
