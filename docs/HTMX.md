# HTMX boundaries (binding)

Lokay is a **CLI lokay** (JSON envelopes on stdout). If a hypermedia UI is
added later, it follows these rules — no hidden SPA.

## Rules

1. **Server owns state.** Mutations (POST/PUT/PATCH/DELETE) are decided on the
   server and return **HTML fragments**, not JSON for client-side re-render of
   chrome or domain UI.
2. **Fragments match partials.** Response HTML reuses the same partial template
   shape the page already targets (`hx-target` / swap into a stable region).
3. **Stable targets.** Prefer fixed element `id`s with `hx-target="#…"` and an
   explicit `hx-swap`. Do not drive swaps via brittle DOM walking.
4. **Progressive enhancement.** Forms and links work without JavaScript where
   practical: real `action`/`method` (and GET links) first; HTMX attributes are
   additive.
5. **No client template SPA.** Ban React/Vue/Svelte/Angular (and similar) for
   product chrome. Ban “fetch JSON → fill template in the browser” for core
   shell or primary domain views.
6. **CLI JSON stays CLI.** Process envelopes (`envelope.ok` / `envelope.err`) are
   **not** a browser UI data API. Do not wire them into client-side chrome
   rendering.

## Allowed client JS

- **HTMX** for request/swap (prefer same-origin platform assets when a shell
  exists; see [`PLATFORM_UI.md`](PLATFORM_UI.md) — not CDN forks).
- **Alpine** only for local UI (toggles, menus, disclosure) — no business rules
  or server-state mirrors. See [`ALPINE.md`](ALPINE.md).

## Anti-patterns

| Forbidden | Why |
| --- | --- |
| JSON + client templates for core chrome | Hidden SPA; server no longer owns view |
| Global client store of server domain state | Duplicates authority; drift (see [`ALPINE.md`](ALPINE.md)) |
| Forms that only work with JS (`preventDefault` only, no `action`) | Breaks progressive enhancement |
| Custom chrome that reimplements platform shell | Forks product_shell contract |

## Enforcement

- Static guard: `tests/test_htmx_boundaries.py` (no SPA stacks; HTML forms stay
  progressive; no JSON-for-chrome render patterns in product code).
- Alpine guard: `tests/test_alpine_boundaries.py` (local UI only; see
  [`ALPINE.md`](ALPINE.md)).
- Platform stack guard: `tests/test_platform_ui_stack.py` (product_shell +
  same-origin assets; see [`PLATFORM_UI.md`](PLATFORM_UI.md)).
- Agents: prefer HTMX skill defaults when touching any future templates.

CLI-only tree with **no** HTML is compliant: there is no SPA chrome and no
JSON+client-render surface.
