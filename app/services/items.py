"""Verwaltung der Verleihgegenstände."""

from __future__ import annotations

from typing import Any

from ..domain.errors import ValidationError
from ..domain.models import RentalItem
from ..plugins.api import PluginRegistry
from ..repositories.sqlite import ItemRepository, RentalRepository


class ItemService:
    def __init__(
        self,
        items: ItemRepository,
        rentals: RentalRepository,
        registry: PluginRegistry,
    ) -> None:
        self._items = items
        self._rentals = rentals
        self._registry = registry

    # ------------------------------------------------------------------
    def list_items(
        self,
        include_inactive: bool = False,
        type_key: str | None = None,
    ) -> list[dict[str, Any]]:
        rented_ids = {rental.item_id for rental in self._rentals.open_rentals()}
        result = []
        for item in self._items.list(include_inactive=include_inactive):
            if type_key and item.type_key != type_key:
                continue
            payload = item.to_dict()
            payload["status"] = self._status_of(item, rented_ids)
            result.append(payload)
        return result

    def get_item(self, item_id: int) -> dict[str, Any]:
        item = self._items.get(item_id)
        rented_ids = {rental.item_id for rental in self._rentals.open_rentals()}
        payload = item.to_dict()
        payload["status"] = self._status_of(item, rented_ids)
        payload["history"] = [
            rental.to_dict()
            for rental in self._rentals.list(item_id=item_id)
        ]
        return payload

    def available_items(
        self, start=None, days: int = 1, type_key: str | None = None
    ) -> list[dict[str, Any]]:
        """Gegenstände, die im gewünschten Zeitraum frei sind."""
        from datetime import date, timedelta

        start = start or date.today()
        end = start + timedelta(days=max(int(days), 1))
        blocked: set[int] = set()
        for item in self._items.list():
            if self._rentals.overlapping(item.id, start, end):
                blocked.add(item.id)
        return [
            payload
            for payload in self.list_items(type_key=type_key)
            if payload["id"] not in blocked
        ]

    # ------------------------------------------------------------------
    def create_item(self, data: dict[str, Any]) -> RentalItem:
        item = self._registry.build_item(
            data.get("type_key", ""),
            name=data.get("name", ""),
            category=data.get("category", ""),
            daily_rate=data.get("daily_rate", 0),
            attributes=data.get("attributes") or {},
        )
        return self._items.add(item)

    def update_item(self, item_id: int, data: dict[str, Any]) -> RentalItem:
        existing = self._items.get(item_id)
        new_type = data.get("type_key")
        if new_type and new_type != existing.type_key:
            raise ValidationError(
                "Der Verleihtyp eines bestehenden Gegenstands kann nicht geändert werden."
            )

        merged_attributes = {**existing.attributes, **(data.get("attributes") or {})}
        updated = self._registry.build_item(
            existing.type_key,
            id=existing.id,
            name=data.get("name", existing.name),
            category=data.get("category", existing.category),
            daily_rate=data.get("daily_rate", existing.daily_rate),
            attributes=merged_attributes,
            active=data.get("active", existing.active),
            created_at=existing.created_at,
        )
        return self._items.update(updated)

    def delete_item(self, item_id: int) -> dict[str, Any]:
        """Löscht, wenn möglich – sonst wird der Gegenstand deaktiviert.

        Ein Gegenstand mit Verleihhistorie darf nicht verschwinden, sonst
        wären alte Vorgänge nicht mehr nachvollziehbar.
        """
        item = self._items.get(item_id)
        if self._items.rental_count(item_id) > 0:
            item.active = False
            self._items.update(item)
            return {
                "deleted": False,
                "deactivated": True,
                "message": "Gegenstand hat Verleihhistorie und wurde deaktiviert.",
            }
        self._items.delete(item_id)
        return {"deleted": True, "deactivated": False, "message": "Gegenstand gelöscht."}

    # ------------------------------------------------------------------
    @staticmethod
    def _status_of(item: RentalItem, rented_ids: set[int]) -> str:
        if not item.active:
            return "inactive"
        return "rented" if item.id in rented_ids else "available"
