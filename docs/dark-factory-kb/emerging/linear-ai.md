# Linear Agent — coding sessions

**Archetype:** Product-system-native issue→PR mill (C)  
**Notable:** Closes the loop *inside* the issue tracker.

## URLs
- https://linear.app/now/coding-sessions-for-linear-agent
- Changelog 2026-06-11: https://linear.app/changelog/2026-06-11-coding-sessions
- https://linear.app/

## Mechanism notes
- **Coding sessions:** Assign issue to Linear Agent (or invoke from chat/comment/Slack) → agent reads issue + discussion + customer requests + Code Intelligence → investigates codebase → proposes approach → writes code in **cloud** using harnesses like **Claude Code or Codex** → opens PR / returns Diffs in Linear.
- **Triage automation:** Can auto-tag Linear Agent on triage so work starts without a human handoff. MCP to Sentry/Datadog/etc. for evidence.
- **Diffs:** Structural diff + AI-guided review inside Linear.
- **Internal claim:** Linear uses this to resolve **~30% of incoming bug reports** mostly on first pass (vendor statement).
- **Availability:** Basic/Business/Enterprise; needs GitHub code access + AI credits; admin controls.

## Dark-factory distance
**Among the closest SaaS product mills** for teams already living in Linear: intake and execution share one system. Still human review/merge; strength is reducing *assignment limbo*, not eliminating ownership.

## Polish
Linear Agent robi sesje kodujące (Claude Code/Codex w chmurze) prosto z issue + triage automation. ~30% bugów Linear naprawia u siebie w pierwszym podejściu — mocny wzorzec „tracker = fabryka”.
