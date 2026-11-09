"""HTTP-Endpunkte für Verleihgegenstände."""

from __future__ import annotations

from fastapi import APIRouter, status

from ..domain.dates import parse_iso_date
from .deps import ContainerDep
from .schemas import ItemIn, ItemUpdate, MessageOut

router = APIRouter(prefix="/api/items", tags=["Verleihgegenstände"])


@router.get("", summary="Gegenstände auflisten")
def list_items(
    container: ContainerDep,
    include_inactive: bool = False,
    type_key: str | None = None,
) -> dict:
    return {
        "items": container.items.list_items(
            include_inactive=include_inactive, type_key=type_key
        )
    }


@router.get("/available", summary="Freie Gegenstände für einen Zeitraum")
def list_available(
    container: ContainerDep,
    start: str | None = None,
    days: int = 1,
    type_key: str | None = None,
) -> dict:
    start_date = parse_iso_date(start, "Startdatum")
    return {
        "items": container.items.available_items(
            start=start_date, days=days, type_key=type_key
        )
    }


@router.get("/{item_id}", summary="Gegenstand inkl. Historie")
def get_item(item_id: int, container: ContainerDep) -> dict:
    return container.items.get_item(item_id)


@router.post("", status_code=status.HTTP_201_CREATED, summary="Gegenstand anlegen")
def create_item(payload: ItemIn, container: ContainerDep) -> dict:
    item = container.items.create_item(payload.model_dump())
    return item.to_dict()


@router.put("/{item_id}", summary="Gegenstand bearbeiten")
def update_item(item_id: int, payload: ItemUpdate, container: ContainerDep) -> dict:
    data = {key: value for key, value in payload.model_dump().items() if value is not None}
    item = container.items.update_item(item_id, data)
    return item.to_dict()


@router.delete("/{item_id}", response_model=MessageOut, summary="Gegenstand löschen")
def delete_item(item_id: int, container: ContainerDep) -> dict:
    return container.items.delete_item(item_id)
