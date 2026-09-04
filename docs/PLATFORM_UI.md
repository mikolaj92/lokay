# Platform UI stack (binding)

Lokay is a **CLI lokay with a local read-only FastAPI status host**. The status
host installs app-factory with `install_platform`, extends
`app_factory/product_shell.html`, and serves the platform bundle from the
same-origin `/static/platform` mount. It has no login, account, or admin
surfaces, so my-auth and my-usermanager are intentionally not dependencies.

## Stack (required for the current status chrome)

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

The status host pins the latest immutable app-factory generation from the
upstream [`COMPAT.md`](https://github.com/mikolaj92/app-factory/blob/main/COMPAT.md)
row. Authentication packages are shown only to keep any future identity work on
one compatible row; they are not installed by Lokay today.

| Package | Current COMPAT tag | Lokay usage |
| --- | --- | --- |
| **app-factory** | `v0.6.16` | installed as `app-factory[platform]`; owns `product_shell` and `/static/platform` |
| **my-auth** | `v0.4.8` | not installed; no authentication surface |
| **my-usermanager** | `v0.5.11` | not installed; no account/admin surface |

```toml
dependencies = ["app-factory[platform]"]
[tool.uv.sources]
app-factory = { git = "https://github.com/mikolaj92/app-factory.git", tag = "v0.6.16" }
```

Do not use a local `path`, floating `main`, or mix generations. If identity is
added later, adopt the complete immutable row through app-factory's identity
composer rather than copying installer, session, or route glue into Lokay.

## Smoke

The status route must:

1. Render through `product_shell` with `id="main-content"`.
2. Include same-origin `/static/platform/…` assets for Basecoat, HTMX, and Alpine.
3. Contain **no** CDN markers for the core stack.
4. Keep login, account, and admin routes absent until identity is explicitly added.

## Anti-patterns

| Forbidden | Why |
| --- | --- |
| CDN for htmx / alpine / basecoat | Breaks same-origin platform contract |
| Host-forked sidebar/header/theme boot | Diverges from product_shell |
| React/SPA chrome | Hidden SPA; see `HTMX.md` |
| Adding identity packages without identity routes | Dead dependency; status-only host stays unauthenticated |

## Enforcement

- Static guard: `tests/test_platform_ui_stack.py`
- Related: `tests/test_htmx_boundaries.py`, `tests/test_alpine_boundaries.py`
- Upstream matrix: app-factory `COMPAT.md` (host rule + BOM table)
