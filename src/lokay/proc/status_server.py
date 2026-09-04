"""One job: serve the local, read-only Lokay status dashboard."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from app_factory.platform import MenuItem, PlatformConfig, PlatformPaths, PlatformUser, build_platform_context, install_platform
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from lokay.status_dashboard import dashboard_snapshot

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))
# The Python snapshot schema and its template form one release. During a live
# checkout fast-forward, reloading only the template can mix two releases and
# turn a healthy read-only page into HTTP 500. launchd restart loads both.
TEMPLATES.env.auto_reload = False
PLATFORM = PlatformConfig(
    app_name="Lokay",
    brand_href="/",
    brand_meta="wyniki",
    menu=(MenuItem("Wyniki", "/", key="overview", use_htmx=True),),
    htmx_nav=True,
    paths=PlatformPaths(account=""),
    show_register=False,
)
LOCAL_OPERATOR = PlatformUser(display_name="Operator lokalny", user_id="local")


def create_app(*, config_path: str | None = None) -> FastAPI:
    """Create an observational app. Requests never survey GitHub or mutate the lokay."""
    app = FastAPI(title="Lokay · Wyniki", docs_url=None, redoc_url=None)
    install_platform(app, environments=[TEMPLATES.env], config=PLATFORM)

    @app.get("/health")
    def health() -> dict[str, Any]:
        data = dashboard_snapshot(config_path, history_limit=1)
        status = data["status"]
        return {"ok": bool(status.get("ok")), "health": status.get("health"), "generated_at": data["generated_at"]}

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request) -> HTMLResponse:
        data = dashboard_snapshot(config_path)
        context = {
            "request": request,
            "page_title": "Wyniki Lokaya",
            "nav_active": "overview",
            "data": data,
            **build_platform_context(PLATFORM, user=LOCAL_OPERATOR, current_path=request.url.path),
        }
        return TEMPLATES.TemplateResponse(request, "lokay/status.html", context)

    return app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-status-server")
    parser.add_argument("--config")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args(argv)
    import uvicorn

    uvicorn.run(create_app(config_path=args.config), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
