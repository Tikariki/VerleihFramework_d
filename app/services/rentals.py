"""Verleih- und Rückgabeprozesse."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from ..domain.dates import parse_iso_date
from ..domain.errors import ConflictError, ItemUnavailableError, ValidationError
from ..domain.models import Rental
from ..pricing.base import PriceQuote
from ..pricing.service import PricingService
from ..repositories.sqlite import CustomerRepository, ItemRepository, RentalRepository


class RentalService:
    def __init__(
        self,
        rentals: RentalRepository,
        items: ItemRepository,
        customers: CustomerRepository,
        pricing: PricingService,
    ) -> None:
        self._rentals = rentals
        self._items = items
        self._customers = customers
        self._pricing = pricing

    # ------------------------------------------------------------------
    def quote(self, data: dict[str, Any]) -> PriceQuote:
        item = self._items.get(self._required_id(data, "item_id"))
        days = data.get("days", 1)
        start_date = parse_iso_date(data.get("start_date"), "Verleihbeginn") or date.today()
        customer_id = data.get("customer_id")
        customer = self._customers.get(int(customer_id)) if customer_id else None
        return self._pricing.quote(item, days, start_date, customer)

    def create_rental(self, data: dict[str, Any]) -> Rental:
        item_id = self._required_id(data, "item_id")
        customer_id = self._required_id(data, "customer_id")

        item = self._items.get(item_id)
        customer = self._customers.get(customer_id)

        if not item.active:
            raise ItemUnavailableError(
                f"'{item.name}' ist deaktiviert und kann nicht verliehen werden."
            )
        if not customer.has_id_document:
            raise ConflictError(
                f"{customer.full_name} hat keinen Ausweis hinterlegt. "
                "Ohne Identitätsnachweis ist keine Verleihung möglich."
            )

        start_date = parse_iso_date(data.get("start_date"), "Verleihbeginn") or date.today()
        quote = self._pricing.quote(item, data.get("days", 1), start_date, customer)
        end_date = start_date + timedelta(days=quote.days)

        conflicts = self._rentals.overlapping(item_id, start_date, end_date)
        if conflicts:
            busy_until = conflicts[0].due_date
            raise ItemUnavailableError(
                f"'{item.name}' ist im Zeitraum {start_date.isoformat()} – "
                f"{end_date.isoformat()} bereits verliehen (frei ab {busy_until.isoformat()})."
            )

        rental = Rental(
            item_id=item_id,
            customer_id=customer_id,
            start_date=start_date,
            days=quote.days,
            daily_rate=item.daily_rate,
            total=quote.total,
            price_lines=[line.as_dict() for line in quote.lines],
            item_name=item.name,
            item_type=item.type_key,
            customer_name=customer.full_name,
        )
        created = self._rentals.add(rental)
        return self._rentals.get(created.id) if created.id else created

    def return_rental(self, rental_id: int, when: datetime | None = None) -> Rental:
        rental = self._rentals.get(rental_id)
        if rental.is_returned:
            raise ConflictError(
                f"Verleihvorgang #{rental_id} wurde bereits am "
                f"{rental.returned_at:%d.%m.%Y} zurückgegeben."
            )
        self._rentals.mark_returned(rental_id, when or datetime.now())
        return self._rentals.get(rental_id)

    # ------------------------------------------------------------------
    def list_rentals(
        self,
        status: str | None = None,
        item_id: int | None = None,
        customer_id: int | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        return [
            rental.to_dict()
            for rental in self._rentals.list(
                status=status, item_id=item_id, customer_id=customer_id, limit=limit
            )
        ]

    def get_rental(self, rental_id: int) -> dict[str, Any]:
        return self._rentals.get(rental_id).to_dict()

    # ------------------------------------------------------------------
    @staticmethod
    def _required_id(data: dict[str, Any], key: str) -> int:
        value = data.get(key)
        if value in (None, ""):
            raise ValidationError(f"'{key}' fehlt.")
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"'{key}' muss eine Zahl sein.") from exc
