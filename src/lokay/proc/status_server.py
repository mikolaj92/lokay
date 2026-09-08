"""One job: serve the local, read-only Lokay status dashboard."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from app_factory.platform import MenuItem, PlatformConfig, PlatformPaths, PlatformUser, build_platform_context, install_platform
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from lokay.status_dashboard import dashboard_snapshot
from lokay.status_artifact import SnapshotUnavailable, read_snapshot

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


def create_app(
    *, config_path: str | None = None, snapshot_path: Path | None = None,
    max_snapshot_age: float = 120,
) -> FastAPI:
    """Create an observational app. Requests never survey GitHub or mutate the lokay."""
    app = FastAPI(title="Lokay · Wyniki", docs_url=None, redoc_url=None)
    install_platform(app, environments=[TEMPLATES.env], config=PLATFORM)

    def read_data(*, history_limit: int = 50) -> dict[str, Any]:
        if snapshot_path is None:
            return dashboard_snapshot(config_path, history_limit=history_limit)
        try:
            return read_snapshot(Path(snapshot_path), max_age=max_snapshot_age)
        except SnapshotUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/health")
    def health() -> dict[str, Any]:
        data = read_data(history_limit=1)
        status = data["status"]
        result = {"ok": bool(status.get("ok")) and not data.get("snapshot_stale", False),
                  "health": status.get("health"), "generated_at": data["generated_at"]}
        if snapshot_path is not None:
            result.update({key: data[key] for key in ("snapshot_stale", "snapshot_age_seconds")})
        return result

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request) -> HTMLResponse:
        data = read_data()
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
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--max-snapshot-age", type=float, default=120)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args(argv)
    import uvicorn

    import math

    if not math.isfinite(args.max_snapshot_age) or args.max_snapshot_age <= 0:
        parser.error("--max-snapshot-age must be finite and positive")
    uvicorn.run(create_app(config_path=args.config, snapshot_path=args.snapshot,
                           max_snapshot_age=args.max_snapshot_age),
                host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
