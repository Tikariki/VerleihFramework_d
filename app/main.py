"""FastAPI-Anwendung des Verleihsystems.

Die App ist eine reine HTTP-Fassade: Sie nimmt Anfragen an, ruft Services
auf und übersetzt fachliche Fehler in HTTP-Statuscodes. Geschäftslogik
liegt ausschließlich in ``app/services``.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import __version__
from .api import routes_customers, routes_items, routes_meta, routes_rentals
from .config import Settings
from .container import build_container
from .domain.errors import DomainError

BASE_DIR = Path(__file__).resolve().parent


def create_app(settings: Settings | None = None) -> FastAPI:
    container = build_container(settings)

    app = FastAPI(
        title="VerleihFramework",
        version=__version__,
        description=(
            "Ski-Verleih mit erweiterbarer Plugin-Architektur. "
            "Weitere Verleiharten (Bike, Snowboard, ...) werden als Plugin ergänzt."
        ),
    )
    app.state.container = container
    app.state.templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

    for module in (routes_items, routes_customers, routes_rentals, routes_meta):
        app.include_router(module.router)

    @app.exception_handler(DomainError)
    async def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.error_code, "message": exc.message},
        )

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def dashboard_page(request: Request) -> HTMLResponse:
        return app.state.templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"version": __version__, "currency": container.settings.currency},
        )

    return app
