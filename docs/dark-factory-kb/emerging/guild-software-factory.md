# Guild.ai — Software Factory

**Archetype:** Commercialised internal-style mill (E)  
**Rare public metrics** for autonomous share of merged PRs.

## URLs
- https://www.guild.ai/blog/product/introducing-guild-software-factory (2026-09-03)
- https://www.guild.ai/

## Mechanism notes
Pipeline of **specialized agents**, not one giant coder:
1. **Dispatcher** — GitHub/Jira events; `guild-auto` label triggers full flow  
2. **Planner** — issue → implementation plan (scoping quality dominates reliability)  
3. **Implementer** — sandboxed coding; runs repo linters/types/tests; draft PR  
4. **Reviewer** — *separate* agent reviews; promotes from draft / factory-approved  
5. **Maintenance:** Conflict Resolver, Janitor (stuck jobs), Code Health, Test Triage  

**Human rule (explicit):** Factory does **not** merge its own PRs. “Agents do the work. People own the outcome.”

### Claimed internal results (vendor, Guild’s own codebase)
- 34% of merged PRs written autonomously by Factory  
- 56% of code fixes from Factory; 70% of auto-detected-issue fixes; 81% of log-triage fixes  
- 75% Factory PRs accepted; 91% of merged Factory PRs need no engineer commits  
- 25% of alerts → fix PR within 90 minutes  
- ~$12 model spend per merged Factory PR; some time-to-fix −97%

Intake also from production log-triage agents creating issues that Factory picks up — classic dark-mill feedback loop.

## Dark-factory distance
**Closest public *productised* E-pattern** after big-co internals. Still not zero-limbo (merge gate). Blueprint for “what serious eng orgs structure.”

## Polish
Guild Software Factory = wyspecjalizowani agenci (dispatcher→plan→implement→review + janitorzy) z sandboxem; 34% merge’y u siebie, bez auto-merge. To jest komercyjny szablon „prawdziwego” młyna.
