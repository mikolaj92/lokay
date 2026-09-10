# Full-app factories: Bolt.new, v0, Lovable (+ peers)

**Archetype:** Prompt → runnable app (D)  
**Explicitly different from issue→PR mills (C/E).**

## URLs
- Bolt.new (StackBlitz / WebContainers): https://bolt.new/
- v0 by Vercel: https://v0.dev/ (enterprise git-workflow relaunch narrative 2026)
- Lovable: https://lovable.dev/ (ownership/export docs emphasize low lock-in + GitHub sync)
- Portability benchmarks (secondary): https://www.builderproof.org/benchmarks/ai-app-builder-code-ownership-2026-portability-leaderboard

## Mechanism notes
| Tool | Mechanism sketch | Portability notes |
|------|------------------|-------------------|
| **Bolt.new** | In-browser full stack via **WebContainers**; agent writes/runs Node app live; export zip / GitHub | Standard Vite/Next-ish code travels; WebContainer is *dev* runtime, not your prod lock-in |
| **v0** | UI/React/Next generation, shadcn-heavy; 2026 push toward production + git workflows | Front-end portable; historically weaker as full backend factory |
| **Lovable** | Full-stack agent builder; often Supabase-backed; two-way GitHub | Strong written ownership stance; backend coupling via Supabase patterns |

**Shared D-tier properties:** Natural-language → working preview fast; verification is “does the preview run?” more than “does monorepo CI + policy pass?”; humans still product-spec and harden for production.

**Adjacent names:** Cursor-like IDEs are *not* in this bucket; RationalGo and similar “code generator” builders compete with Bolt/Lovable on exportability.

## Dark-factory distance
**Wrong tool for dark brownfield mills.** Closest dark-factory *feeling* for greenfield MVP velocity. Serious eng orgs may use D-tier for spikes, then graduate artifacts into C/E pipelines.

## Polish
Bolt/v0/Lovable = fabryki *nowych* aplikacji z promptu (WebContainer/UI-first/full-stack). To nie to samo co młyn issue→sandbox→PR na żywym kodzie produkcyjnym — nie mieszaj kategorii w researchu.
