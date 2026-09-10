# Factory.ai (factory.ai)

**Archetype:** Issue→PR mill → org software factory (C→E)  
**Closest dark-factory claim among commercial platforms.**

## URLs
- https://factory.ai/
- https://factory.ai/product/droids
- https://factory.ai/product/missions
- https://factory.ai/news/software-factory — “Factory 2.0: From coding agents to software factories”
- https://factory.ai/news/missions-architecture — How Missions work
- https://factory.ai/news/series-c — $150M Series C, ~$1.5B valuation (Khosla-led; Sequoia, Blackstone, Insight, …)

## Mechanism notes
- **Droids:** Autonomous coding agents — plan, write, test, ship; surfaces: terminal, IDE, browser, Slack, CLI. “One prompt to PR.” Model-routing across Claude/GPT/Gemini/etc. Explicit permission / autonomy dials (supervised → autonomous).
- **Missions:** Multi-agent, multi-day orchestration. Decompose goal → features → milestones; spawn fresh-context workers per feature (tests-first then implement); validators (scrutiny + user-testing black-box); orchestrator opens fix features until milestone validation passes. Parallel Droids; multi-repo migrations called out.
- **Software factory loop (vendor thesis):** external signals (bugs, chat, feedback, requirements) → triage/plan → build/test/review/secure/ship → monitor → more signals. Layers: simple Droids/skills → Automations → remote Droid Computers → Missions.
- **Headless:** `droid exec` for pipeline automation; Factory Desktop for local system access.
- **Enterprise posture:** Named customers in Series C note (Nvidia, Adobe, EY, Palo Alto Networks, Adyen). Governance / agent-readiness measurement emphasized in roadmap.

## Dark-factory distance
**Near the commercial frontier of E.** Product language matches org mills (signals→ship loop, multi-agent validation, headless). Still typically human-gated for high-risk merge/deploy; autonomy is configurable, not absolute.

## Polish (1–2 zdania)
Factory buduje platformę „software factory”: Droids jako jednostki wykonawcze + Missions jako długotrwała orkiestracja multi-agent. Najbliższy komercyjny odpowiednik wewnętrznych młynów typu Stripe/Uber — z dialem autonomii zamiast „tylko IDE”.
