# Replit Agent

**Archetype:** Full-app / environment-native factory (D)  
**Not** a brownfield issue→PR mill by default.

## URLs
- https://replit.com/ (Agent product surfaces in Replit IDE)
- Comparisons / ownership: e.g. https://techsifted.com/roundups/best-ai-app-builders-2026/

## Mechanism notes
- Prompt / goal → agent builds and iterates **inside Replit’s hosted env** (Nix/.replit shaped runtime, deployments, often platform DB/auth).
- Strong for education, experiments, quick full-stack apps; weaker as portable brownfield mill for large existing monorepos.
- Export via zip/GitHub possible; **runtime coupling** (Replit DB, auth, deploy assumptions) is the lock-in risk — code is more portable than the operating envelope.
- Effort/usage-based cost surprise is a recurring complaint class in agent builders (shared with other D-tier tools).

## Dark-factory distance
**High autonomy for greenfield D.** Low fit for “queue of Jira tickets against prod services” unless you deliberately constrain Agent to repo tasks and externalize review — still not Stripe-shaped.

## Polish
Replit Agent = fabryka aplikacji w hostowanym środowisku, nie młyn ticket→PR na istniejącym monorepo. Inna kategoria niż Devin/Factory/Linear.
