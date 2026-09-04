# Alpine boundaries (binding)

Lokay is a **CLI lokay** (JSON envelopes on stdout). If a hypermedia UI is
added later, Alpine may power **local presentation state only** — never an
app-wide client store of server/domain data.

## Rules

1. **Local UI state only.** Alpine is for toggles, menus, disclosure panels,
   tabs, small transitions, and inline affordances (`x-data`, `x-show`,
   `x-bind`, `x-on`, `x-model`, `x-transition`, `x-cloak`).
2. **No app-wide Alpine store.** Do **not** introduce `Alpine.store(...)` or
   `$store…` for product chrome / domain state unless a store already exists
   in this tree (today: none — so none is the default forever until a human
   consciously adds one).
3. **No server-state mirrors.** Do not fetch JSON (or CLI envelopes) into
   Alpine and treat that as the source of truth for lists, tickets, agents,
   or other domain objects. Server HTML (and HTMX fragments) own that view.
4. **No business rules / validation duplication.** Required fields, triage
   decisions, permissions, and merge policy stay on the server. Alpine may
   only improve presentation (e.g. show/hide a field group).
5. **Menus and dialogs are keyboard accessible.** When Alpine drives a menu
   or dialog:
   - Use real buttons / native `<dialog>` or correct ARIA (`role="dialog"`,
     `aria-expanded`, `aria-controls` as appropriate).
   - Close on **Escape**.
   - Keep focus usable (open → focus inside; close → return to the control).
   - Do not rely on hover-only or click-only without keyboard paths.

## Allowed

| Use | Example |
| --- | --- |
| Disclosure | `x-data="{ open: false }"` + button toggles a panel |
| Menu open/close | Local `open` boolean; Escape sets `open = false` |
| Dialog open/close | `<dialog>` or `role="dialog"` with Escape + focus |
| Small transitions | `x-transition` on the same local component |

## Forbidden

| Pattern | Why |
| --- | --- |
| `Alpine.store('…')` / `$store.…` for domain data | App-wide store; duplicates server authority |
| Alpine holding issue/PR/repo lists from fetch/JSON | Server-state mirror; hidden SPA |
| Client-side triage/validation that replaces server checks | Business-rule duplication |
| Menu/dialog without Escape / keyboard path | Inaccessible chrome |

## Enforcement

- Static guard: `tests/test_alpine_boundaries.py` (no global store; Alpine
  menus/dialogs require Escape + accessible markup when present).
- Platform stack: same-origin Alpine via app-factory when chrome exists —
  [`PLATFORM_UI.md`](PLATFORM_UI.md).
- Agents: Alpine skill defaults — local state only; pair with [`HTMX.md`](HTMX.md).

CLI-only tree with **no** Alpine is compliant: there is no store and no
inaccessible Alpine menu/dialog.
