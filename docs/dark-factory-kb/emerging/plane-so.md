# Plane.so — AI + Cursor agent

**Archetype:** Open-ish project management → agent handoff (lighter C)  
**Contrast:** Self-hostable alternative vibe vs Linear SaaS depth.

## URLs
- https://plane.so/blog/introducing-mcp-connectors-and-cursor-agent
- https://plane.so/

## Mechanism notes
- **Plane AI:** Multi-step actions; **Auto-mode** skips per-step confirmation.
- **Cursor agent:** Assign work items → execute changes in codebase via Cursor integration; link branches; keep Plane state in sync.
- **MCP:** Plane ships native MCP server (external agents read/write workspace). **MCP connectors** pull *in* tools (Linear, Granola, …) for Plane AI to call.
- **SCM:** GitHub, GitLab, **Bitbucket**.
- **Packaging:** AI/Auto-run/MCP connectors/Cursor agent on Pro+ class plans per blog table.

## Dark-factory distance
**Lighter mill glue** than Linear coding sessions or Factory Missions. Useful open/self-host-friendly control plane; execution quality depends on Cursor (or other MCP agents) behind it.

## Polish
Plane łączy work itemy z agentem Cursor + MCP (dwukierunkowo). Lżejszy / bardziej self-host niż Linear coding sessions — dobry klej, nie pełna fabryka sama w sobie.
