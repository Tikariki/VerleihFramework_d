"""Kennzahlen für das Dashboard."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from ..plugins.api import PluginRegistry
from ..pricing.service import PricingService
from ..repositories.sqlite import CustomerRepository, ItemRepository, RentalRepository


class DashboardService:
    def __init__(
        self,
        items: ItemRepository,
        customers: CustomerRepository,
        rentals: RentalRepository,
        registry: PluginRegistry,
        pricing: PricingService,
    ) -> None:
        self._items = items
        self._customers = customers
        self._rentals = rentals
        self._registry = registry
        self._pricing = pricing

    def stats(self, today: date | None = None) -> dict[str, Any]:
        today = today or date.today()
        month_start = today.replace(day=1)

        items = self._items.list(include_inactive=True)
        active_rentals = self._rentals.open_rentals()
        rented_ids = {rental.item_id for rental in active_rentals}

        available = [item for item in items if item.active and item.id not in rented_ids]
        inactive = [item for item in items if not item.active]

        overdue = [rental for rental in active_rentals if rental.is_overdue(today)]
        due_week = self._rentals.due_between(today, today + timedelta(days=7))
        due_today = [rental for rental in due_week if rental.due_date == today]

        customers = self._customers.list()

        by_type = []
        for type_key, item_type in self._registry.item_types.items():
            type_items = [item for item in items if item.type_key == type_key and item.active]
            by_type.append(
                {
                    "type_key": type_key,
                    "label": item_type.display_name,
                    "total": len(type_items),
                    "rented": sum(1 for item in type_items if item.id in rented_ids),
                }
            )

        return {
            "date": today.isoformat(),
            "items": {
                "total": len(items),
                "active": len(items) - len(inactive),
                "available": len(available),
                "rented": len([item for item in items if item.id in rented_ids]),
                "inactive": len(inactive),
                "by_type": by_type,
            },
            "customers": {
                "total": len(customers),
                "with_document": sum(1 for c in customers if c.has_id_document),
            },
            "rentals": {
                "active": len(active_rentals),
                "overdue": len(overdue),
                "due_today": len(due_today),
                "due_this_week": len(due_week),
                "total": len(self._rentals.list()),
            },
            "revenue": {
                "today": str(self._rentals.revenue_between(today, today)),
                "month": str(self._rentals.revenue_between(month_start, today)),
                "total": str(self._rentals.revenue_between(date(1970, 1, 1), today)),
            },
            "due_soon": [rental.to_dict() for rental in due_week[:10]],
            "overdue": [rental.to_dict() for rental in overdue[:10]],
            "recent_rentals": [
                rental.to_dict() for rental in self._rentals.list(limit=8)
            ],
            "price_rules": self._pricing.describe(),
        }
