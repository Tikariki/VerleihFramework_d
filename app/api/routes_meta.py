"""Meta- und Dashboard-Endpunkte.

``/api/meta`` ist die Schnittstelle für Erweiterbarkeit im Frontend: Die
Oberfläche baut ihre Formulare aus den hier gemeldeten Verleihtypen und
Ausweistypen. Ein neues Plugin erscheint dadurch automatisch in der UI.
"""

from __future__ import annotations

from fastapi import APIRouter

from .deps import ContainerDep

router = APIRouter(prefix="/api", tags=["Meta/Dashboard"])


@router.get("/meta", summary="Plugins, Verleihtypen, Ausweistypen, Preisregeln")
def meta(container: ContainerDep) -> dict:
    payload = container.registry.describe()
    payload["currency"] = container.settings.currency
    payload["pricing_rules"] = container.pricing.describe()
    return payload


@router.get("/dashboard", summary="Kennzahlen für das Dashboard")
def dashboard(container: ContainerDep) -> dict:
    return container.dashboard.stats()


@router.get("/health", summary="Healthcheck")
def health() -> dict:
    return {"status": "ok"}
