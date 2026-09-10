# How serious eng orgs structure an “AI coding mill” (2024–2026 blogs)

**Archetype:** True E patterns — queue, sandboxes, hybrid deterministic+agent loops, human merge ownership.

## Stripe — Minions
- **URLs:**  
  - https://stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents  
  - https://stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents-part-2  
- **Mechanism:** Fully **unattended** one-shot agents on pre-warmed **devboxes** (~10s spin-up, same machines humans use; isolated from prod/internet → fewer permission prompts). Fork of Block **goose** customized for Stripe LLM infra; **interleave agentic steps with deterministic code** (git, linters, required tests always run). MCP for networked tools.  
- **Output:** ~1,000→**1,300+ PRs/week** with **zero human-written code**, still **human-reviewed**.  
- **Lesson:** Dark factory rides on years of human DX investment (devboxes, CI, codegen). Unattended ≠ ungoverned.

## Uber — Software Factory (efficiency)
- **URL:** https://www.uber.com/us/en/blog/efficient-software-factory/  
- **Mechanism:** AI in every SDLC phase; **>70% PRs** attributed to local/cloud agents; **3,600+ agent skills**; **30K+ skill executions/day**. Shift from interactive sessions → **managed agents** (review, self-healing CI, E2E PRs with visual validation, on-call triage, maintenance) with human review/escalation. Four-layer cost model; specialized agents + evals + Pareto model routing beat “every eng’s terminal session.”  
- **Lesson:** Factory is a **fleet + FinOps + eval** problem, not a single mega-agent.

## Ramp — Inspect
- **URL:** https://newsletter.pragmaticengineer.com/p/why-ramp-built-inspect  
- **Mechanism:** Internal background coding agent on **remote dev environments** (OpenCode harness HTTP API, model-agnostic). Central config beats local setup drift. Deep internal tool/DB/CI access for verification third-party harnesses lack.  
- **Metrics:** **~75% of merged PRs** from Inspect sessions; tiny platform team (~5.5 FTE) + wide internal contribution.  
- **Peers named:** Block Goose, Stripe Minions, Shopify **River**.

## Guild — Software Factory
- See [guild-software-factory.md](./guild-software-factory.md) — specialized pipeline + maintenance agents; no auto-merge.

## AFK / community mill patterns
- **Sandcastle AFK loop:** https://medium.com/heybe-ai/i-built-an-afk-coding-agent-loop-on-sandcastle-issue-merge-d1998d7d4252 — issue labels drive implement → host opens PR → agent review → merge → unblock next; bright line `ready-for-agent` vs `ready-for-human`.  
- **Loop + graph engineering:** https://blog.gopenai.com/building-coding-agent-workflows-with-loop-engineering-5686587501e1 — GitHub Issues as shared queue; planner/implementer/tester/evaluator nodes; learning ledger after merge.  
- **Murray Cole “What is a software factory?”:** https://murraycole.com/posts/software-factory — specs quality, sandbox back-pressure (linters/Semgrep fail fast inside agent loop), human risk ownership.  
- **Hashnode roundup:** https://hashnode.com/blog/ai-software-factory-tools — buy platform vs assemble parts vs self-host; intake→isolation→implement→verify→PR checklist.

## Canonical mill architecture (synthesis)

```
[signals: issues, alerts, logs, customers]
        → triage / label (auto or human)
        → queue (forge issues or SQLite/Temporal)
        → sandbox/devbox/orb (ephemeral, creds scoped)
        → planner agent (fresh context)
        → implementer agent (+ deterministic hooks)
        → verify (unit/lint/type/browser)
        → reviewer agent (separate from writer)
        → draft PR + evidence
        → HUMAN MERGE GATE (almost always)
        → janitor / conflict / learn ledger
```

**What serious orgs refuse:** writer-agent self-approving merge to prod; unbounded internet from sandbox; one infinite-context mega-agent for all roles.

## Dark-factory distance
These internals are the **reference dark factories**. Commercial tools (Factory.ai, Linear, Devin, Guild) approximate pieces; few customers match Stripe/Ramp attach rates without the underlying DX platform.

## Polish
Poważne orgs (Stripe Minions, Uber Factory, Ramp Inspect): kolejka + ciepłe sandboxy + deterministyczne haki + osobny review + człowiek na merge. To jest złoty standard „dark factory” na 2025–2026 — nie sam Copilot w IDE.
