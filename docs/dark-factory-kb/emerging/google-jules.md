# Google Jules

**Archetype:** Async issue→PR mill (C)  
**Model spine:** Gemini family (2.5 Pro / 3 Pro per plan tier messaging).

## URLs
- https://jules.google/

## Mechanism notes
- Select GitHub repo/branch + prompt, or label issues with **`jules`** → clone to **Cloud VM** → plan (user can approve) → diff → PR.
- Positioned for chores humans don’t want: bugfix, version bumps, tests, small features.
- **Concurrency/quota tiers:** Free-ish entry (e.g. 15 tasks/day, 3 concurrent in marketing) up through higher daily/concurrent limits and priority Gemini 3 Pro access.
- GA narrative around I/O 2026 in secondary “software factory tools” roundups — same shape as Copilot coding agent / Cursor background agents: task in, VM, PR out; lighter verification/credential story than dedicated factory platforms.

## Dark-factory distance
**Solid commodity C.** Easy experiment if already on GitHub. Not an org-wide self-healing mill without extra wiring (triage bots, merge policy, eval harness).

## Polish
Jules = Google’owy async agent (Gemini) na VM → plan → PR, także z labelki na issue. Tani sposób sprawdzić kształt młyna; nie zastępuje Stripe/Guild-owego stacka governance.
