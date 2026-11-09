"""Kunden- und Ausweisverwaltung."""

from __future__ import annotations

from typing import Any

from ..domain.errors import ConflictError, ValidationError
from ..domain.models import Customer, IdDocument
from ..plugins.api import PluginRegistry
from ..repositories.sqlite import CustomerRepository, RentalRepository


class CustomerService:
    def __init__(
        self,
        customers: CustomerRepository,
        rentals: RentalRepository,
        registry: PluginRegistry,
    ) -> None:
        self._customers = customers
        self._rentals = rentals
        self._registry = registry

    # ------------------------------------------------------------------
    def list_customers(self) -> list[dict[str, Any]]:
        active_ids = {rental.customer_id for rental in self._rentals.open_rentals()}
        result = []
        for customer in self._customers.list():
            payload = self._to_dict(customer)
            payload["has_active_rental"] = customer.id in active_ids
            result.append(payload)
        return result

    def get_customer(self, customer_id: int) -> dict[str, Any]:
        customer = self._customers.get(customer_id)
        payload = self._to_dict(customer)
        payload["history"] = [
            rental.to_dict() for rental in self._rentals.list(customer_id=customer_id)
        ]
        return payload

    # ------------------------------------------------------------------
    def create_customer(self, data: dict[str, Any]) -> Customer:
        customer = Customer(
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            email=data.get("email", "") or "",
            phone=data.get("phone", "") or "",
            id_document=self._build_document(data),
        )
        return self._customers.add(customer)

    def update_customer(self, customer_id: int, data: dict[str, Any]) -> Customer:
        existing = self._customers.get(customer_id)
        customer = Customer(
            id=existing.id,
            first_name=data.get("first_name", existing.first_name),
            last_name=data.get("last_name", existing.last_name),
            email=data.get("email", existing.email) or "",
            phone=data.get("phone", existing.phone) or "",
            id_document=self._build_document(data, fallback=existing.id_document),
            created_at=existing.created_at,
        )
        return self._customers.update(customer)

    def attach_document(
        self,
        customer_id: int,
        *,
        type_key: str,
        number: str,
        file_name: str | None = None,
    ) -> Customer:
        """Hinterlegt oder ersetzt den Ausweis eines Kunden."""
        customer = self._customers.get(customer_id)
        document = self._validate_document(type_key, number, file_name)
        customer.id_document = document
        return self._customers.update(customer)

    def delete_customer(self, customer_id: int) -> None:
        self._customers.get(customer_id)
        if self._customers.rental_count(customer_id) > 0:
            raise ConflictError(
                "Der Kunde hat Verleihvorgänge und kann nicht gelöscht werden."
            )
        self._customers.delete(customer_id)

    # ------------------------------------------------------------------
    def _build_document(
        self,
        data: dict[str, Any],
        fallback: IdDocument | None = None,
    ) -> IdDocument | None:
        type_key = data.get("id_type")
        number = data.get("id_number")

        if type_key is None and number is None:
            return fallback

        if type_key in (None, "") and fallback is not None:
            type_key = fallback.type_key
        if number in (None, "") and fallback is not None:
            number = fallback.number

        if not type_key and not number:
            return None
        return self._validate_document(
            type_key or "",
            number or "",
            data.get("id_file", fallback.file_name if fallback else None),
        )

    def _validate_document(
        self, type_key: str, number: str, file_name: str | None
    ) -> IdDocument:
        doc_type = self._registry.id_document_type(type_key)
        number = (number or "").strip()
        if doc_type.requires_number and not number:
            raise ValidationError(f"Für '{doc_type.label}' ist eine Ausweisnummer nötig.")
        return IdDocument(type_key=doc_type.key, number=number, file_name=file_name)

    @staticmethod
    def _to_dict(customer: Customer) -> dict[str, Any]:
        document = customer.id_document
        return {
            "id": customer.id,
            "first_name": customer.first_name,
            "last_name": customer.last_name,
            "full_name": customer.full_name,
            "email": customer.email,
            "phone": customer.phone,
            "has_id_document": customer.has_id_document,
            "id_document": {
                "type_key": document.type_key,
                "number": document.number,
                "file_name": document.file_name,
            }
            if document
            else None,
            "created_at": customer.created_at.isoformat(timespec="seconds"),
        }
