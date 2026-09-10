# Emerging AI Software Factories — Knowledge Base

**Scope:** Lesser-known / emerging products and internal org practices between assisted IDEs and a true “dark factory” (ticket → sandbox → verify → merge with minimal human limbo).  
**As-of:** 2026-09-10 (Europe/Warsaw). Sources: vendor posts, eng blogs, secondary roundups — treat claims as directional.

## Taxonomy

| Archetype | What it does | Human limbo | Examples |
|-----------|--------------|-------------|----------|
| **A. Assisted IDE** | Pair-program in editor; human drives | High | Cursor Composer, Cody chat, Tabnine autocomplete, Cascade-era Windsurf |
| **B. Interactive agent CLI/IDE** | Multi-file agent with checkpoints | Medium | Amp, Claude Code, Tabnine CLI, Devin Local |
| **C. Issue→PR mill** | Ticket → sandboxed agent → draft PR | Low during run; human at review/merge | Devin Cloud, Jules, Copilot Coding Agent, Linear coding sessions, Guild, Factory Droids/Missions |
| **D. Full-app greenfield factory** | Prompt → runnable app | Low for prototypes; not brownfield | Bolt.new, v0, Lovable, Replit Agent |
| **E. Org software factory / dark mill** | Queue + sandboxes + merge policy + specialist agents | Lowest — humans own outcome/merge | Stripe Minions, Uber Software Factory, Ramp Inspect, Guild |

**Issue→PR mill ≠ full-app factory.** Mills chew existing repos/tickets. Greenfield factories mint new apps from prompts.

## Closest to true dark factory (zero human limbo)

**Honest ranking (closest → furthest):**

1. **Internal mills — Stripe Minions, Ramp Inspect, Uber managed agents, Guild Software Factory** — Continuous intake (alerts/logs/issues), sandboxed unattended runs, specialized planner/implementer/reviewer (+ janitors). **Almost always human-owned merge.** Stripe ~1,300 minion PRs/week with zero human-written lines but human review; Guild deliberately does *not* auto-merge.
2. **Factory.ai Missions + Droids** — Closest *commercial platform* framing to dark factory (signals→ship loop, multi-agent validation, headless `droid exec`).
3. **Linear Agent coding sessions + triage automation** — Tracker-native mill; vendor claims ~30% of *their* bugs auto-fixed first pass.
4. **Devin Cloud / Jules / Copilot Coding Agent** — Mature async issue→PR; human assigns/approves. Cognition folded Windsurf into **Devin Desktop**.
5. **Amp orbs / Tabnine Agents / Augment Intent** — Can run AFK; still “dev orchestrates agents,” not org-wide mills by default.
6. **Bolt / v0 / Lovable / Replit Agent** — High autonomy for *new* apps; weak brownfield dark factories.
7. **Assisted IDE layer** — Furthest from dark factory.

**True zero-human-limbo (auto-merge to prod, no review) is rare** and usually scoped to low-risk classes behind policy. Serious orgs keep the merge gate human even when implementation is fully agentic.

## File index — products

| File | Subject | Archetype |
|------|---------|-----------|
| [factory-ai.md](./factory-ai.md) | Factory.ai — Droids, Missions, Series C | C→E |
| [poolside.md](./poolside.md) | Poolside — *Model* Factory (Laguna); not SDLC mill | Adjacent |
| [magic-dev.md](./magic-dev.md) | Magic.dev — LTM / frontier code models | Adjacent |
| [cognition-devin.md](./cognition-devin.md) | Cognition Devin + Windsurf→Devin Desktop | B+C |
| [amp.md](./amp.md) | Amp (Sourcegraph spinout) | B→C |
| [tabnine-agents.md](./tabnine-agents.md) | Tabnine Agentic Platform + CLI | B→C |
| [windsurf-cascade.md](./windsurf-cascade.md) | Codeium Windsurf Cascade (legacy) | B hist. |
| [replit-agent.md](./replit-agent.md) | Replit Agent | D |
| [bolt-v0-lovable.md](./bolt-v0-lovable.md) | Bolt.new / v0 / Lovable | D |
| [linear-ai.md](./linear-ai.md) | Linear Agent coding sessions | C |
| [plane-so.md](./plane-so.md) | Plane.so Cursor agent + MCP | C light |
| [augment-intent.md](./augment-intent.md) | Augment Intent | B→C |
| [google-jules.md](./google-jules.md) | Google Jules | C |
| [guild-software-factory.md](./guild-software-factory.md) | Guild.ai Software Factory | E |
| [chinese-agents.md](./chinese-agents.md) | Trae, Qoder, ZCode, Kimi, CodeBuddy, … | B→D |
| [european-products.md](./european-products.md) | NeuroCOD, Autonoma, orkestr, Cerebe, orq | C→E / infra |
| [attractor.md](./attractor.md) | StrongDM Attractor (stateful orchestrator mention) | Adjacent |

## File index — practices & OSS

| File | Subject |
|------|---------|
| [internal-practices.md](./internal-practices.md) | Stripe Minions, Uber, Ramp Inspect, Shopify River, AFK loops, blogs 2024–2026 |
| [oss-mills.md](./oss-mills.md) | OpenHands, robotsix-mill, DAGent, OpenFactory, theFactory |

## Mechanism checklist (any factory)

1. Intake (ticket/spec/alert)  2. Isolation (sandbox/devbox/orb)  3. Implementation (agent+tools)  
4. Verification (CI/lint/browser in sandbox)  5. Handoff (draft PR+evidence)  6. Merge policy  7. Maintenance agents (janitor/conflicts/triage)

## Related dirs
`../commercial/` · `../oss/` · `../patterns/`
