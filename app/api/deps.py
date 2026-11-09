"""Gemeinsame Abhängigkeiten der API-Routen."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from ..container import Container


def get_container(request: Request) -> Container:
    """Liefert den Composition Root der laufenden Anwendung."""
    return request.app.state.container


ContainerDep = Annotated[Container, Depends(get_container)]
