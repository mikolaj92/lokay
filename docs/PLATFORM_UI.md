# Platform UI stack (binding)

Lokay is a **CLI mill** (JSON envelopes on stdout). It has **no** hypermedia
host, login, account, or admin surfaces today. If those appear later, this
host must use the **full platform frontend stack** — not half-integrations or
CDN forks.

## Stack (required when any auth/chrome UI exists)

| Layer | Source | Rule |
| --- | --- | --- |
| Chrome frame | `app_factory/product_shell.html` | Hosts **extend** the shell; provide menu data only |
| CSS/JS | app-factory same-origin `/static/platform/...` | Basecoat + HTMX + Alpine + Material Symbols |
| Auth UI | my-auth / my-usermanager via platform partials | No host-forked sidebar/header/theme boot |
| Local UI only | Alpine (`docs/ALPINE.md`) | No app-wide store / server-state mirrors |
| Fragments | HTMX (`docs/HTMX.md`) | Server HTML fragments; no hidden SPA |

Landing pages may differ; **chrome / session / theme / locale / auth** must
match the app-factory COMPAT host rule.

## Same-origin assets only (core stack)

Core chrome assets **must** load from same-origin platform URLs, for example:

- `/static/platform/basecoat-factory.min.css` (or `platform_asset_url('basecoat-css')`)
- `/static/platform/…` for basecoat JS, HTMX, Alpine, Material Symbols

**Forbidden for Basecoat / HTMX / Alpine (and Material Symbols):**

- CDN hosts (`cdn.jsdelivr.net`, `unpkg.com`, `cdnjs.cloudflare.com`, `htmx.org`,
  `alpinejs.dev`, Google Fonts CDN for platform icons)
- Vendored host copies that re-ship the platform stack outside app-factory
- Private “half” bundles (`htmx_alpine.js` style forks)

Optional product extras (charts, etc.) may use app-factory optional CDN helpers
only when they are **not** chrome/core stack — never for htmx/alpine/basecoat.

## product_shell / chrome placement

When auth UI exists, follow app-factory COMPAT chrome placement:

| Surface | Partial | Contents |
| --- | --- | --- |
| Main header | `product_shell` + `platform_theme_locale` | identity/avatar + language + theme toggle |
| Sidebar foot | `platform_auth` | guest Login (+ Register); hidden when signed in |
| Account page | `platform_session` | **Log out** form (only place) |
| No-sidebar shells | `platform_controls` | theme/locale + auth (still no logout in nav) |

Forbidden host forks: identity/avatar in sidebar, theme in sidebar, logout in
nav menu, or logout next to the account name in the header. Do **not** re-copy
theme boot, shell boot, or platform foot templates into this repo.

Detail for shell extension only: issue #13. BOM pin enforcement when packages
are real dependencies: issue #14.

## Pins vs COMPAT matrix

When (and only when) this host grows a FastAPI/hypermedia surface with auth,
pin **immutable tags** aligned with the current app-factory
[`COMPAT.md`](https://github.com/mikolaj92/app-factory/blob/main/COMPAT.md)
row — prefer the latest platform BOM already adopted elsewhere:

| Package | Pin (tag) | Notes |
| --- | --- | --- |
| **app-factory** | `v0.5.19` | `app-factory[platform]`; product_shell + `/static/platform` |
| **my-auth** | `v0.3.23` | Passkey login/register UI |
| **my-usermanager** | `v0.4.5` | Account/admin UI |

Example (do not float `main`):

```toml
dependencies = ["app-factory[platform]"]
[tool.uv.sources]
app-factory = { git = "https://github.com/mikolaj92/app-factory", tag = "v0.5.19" }
# my-auth / my-usermanager: same COMPAT row tags when auth is wired
```

**Today:** lokay has **no** app-factory / my-auth / my-usermanager dependency.
That is correct for a CLI-only mill. Pins above are the target BOM if UI is
added; keep `uv.lock` aligned with tags (not `branch = "main"`) at that time.

## Smoke (when surfaces exist)

Login / account / admin (or equivalent) responses must:

1. Render through `product_shell` (e.g. `id="main-content"`, app shell chrome).
2. Include same-origin `/static/platform/…` links/scripts for Basecoat, HTMX, Alpine.
3. Contain **no** CDN markers for those core assets.

CLI-only tree with **no** HTML and **no** auth routes is compliant: there is
no chrome to fork and no CDN surface.

## Anti-patterns

| Forbidden | Why |
| --- | --- |
| CDN for htmx / alpine / basecoat | Breaks same-origin platform contract |
| Host-forked sidebar/header/theme boot | Diverges from product_shell |
| React/SPA chrome | Hidden SPA; see `HTMX.md` |
| Adding app-factory only to silence an audit without UI | Dead dependency; CLI mill stays CLI |

## Enforcement

- Static guard: `tests/test_platform_ui_stack.py`
- Related: `tests/test_htmx_boundaries.py`, `tests/test_alpine_boundaries.py`
- Upstream matrix: app-factory `COMPAT.md` (host rule + BOM table)
