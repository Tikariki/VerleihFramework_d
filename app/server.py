"""ASGI-Einstiegspunkt für ``uvicorn app.server:app``."""

from __future__ import annotations

from .main import create_app

app = create_app()
