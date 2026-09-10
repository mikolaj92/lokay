# Tabnine Agents + CLI

**Archetype:** Enterprise-governed agentic platform (B→C)  
**Differentiator:** Org-native context + air-gap / VPC, not “vibes IDE.”

## URLs
- https://www.tabnine.com/blog/introducing-the-tabnine-agentic-platform/ (Nov 2025)
- https://www.tabnine.com/blog/introducing-the-tabnine-cli/ (Jan 2026)
- https://www.tabnine.com/platform-cli/
- https://www.tabnine.com/enterprise-context-engine/
- Context Engine essay: https://context.tabnine.com/2026/04/29/code-generation-needs-a-knowledge-graph-not-a-search-index/

## Mechanism notes
- **Tabnine Agents:** Plan/execute/validate multi-step workflows aligned to org codebase, policies, tools. Deploy SaaS / VPC / on-prem / **air-gapped**.
- **Enterprise Context Engine:** Knowledge-*graph* (entities, deps, ADRs, incidents, owners) over RAG-only search. Agents query blast radius, architectural constraints, async-call policies, etc. at generation time. Can ground **external** agents too (Cursor, Copilot, Claude Code) via MCP-style access.
- **Tabnine CLI:** Terminal-native agent — feature impl, cross-file refactor, tests, commands, branches. Interactive confirmation **or “Yolo mode”** (fully autonomous steps). Same backend/governance as platform → works where public agents can’t (air-gap).
- **Positioning:** Less “beat Devin on SWE-bench demos,” more “enterprise can actually turn agents on.”

## Dark-factory distance
**Capable substrate for a mill** inside regulated orgs. Out of box still closer to governed agent CLI than always-on signal→merge factory unless integrated with issue trackers + CI.

## Polish
Tabnine Agents/CLI + Context Engine (graf wiedzy, nie tylko RAG) pod enterprise i air-gap. Dobry kandydat na „młyn w banku/telecomie”; mniej flashy niż Devin, więcej governance.
