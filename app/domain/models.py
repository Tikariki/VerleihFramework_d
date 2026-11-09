"""Domänenmodell des Verleihsystems.

Zentrale Idee: ``RentalItem`` ist die gemeinsame Abstraktion für *alle*
Verleihgegenstände. Konkrete Arten (Ski, Snowboard, Bike, ...) werden als
Unterklassen von Plugins beigesteuert – dieser Code hier kennt sie nicht.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, ClassVar, Sequence, TYPE_CHECKING

from .errors import ValidationError
from .money import money

if TYPE_CHECKING:  # pragma: no cover - nur für Typprüfung
    from ..pricing.base import PricingRule


@dataclass(frozen=True)
class AttributeField:
    """Beschreibung eines typspezifischen Attributs.

    Die Oberfläche baut daraus automatisch die Eingabefelder, die API
    validiert damit – ein neuer Verleihtyp braucht also kein eigenes Formular.
    """

    name: str
    label: str
    kind: str = "text"  # text | number | select | bool
    required: bool = False
    options: tuple[str, ...] = ()
    unit: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "kind": self.kind,
            "required": self.required,
            "options": list(self.options),
            "unit": self.unit,
        }


@dataclass(frozen=True)
class IdDocument:
    """Ausweis eines Kunden."""

    type_key: str
    number: str
    file_name: str | None = None


@dataclass
class Customer:
    first_name: str
    last_name: str
    email: str = ""
    phone: str = ""
    id_document: IdDocument | None = None
    id: int | None = None
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        self.first_name = (self.first_name or "").strip()
        self.last_name = (self.last_name or "").strip()
        if not self.first_name:
            raise ValidationError("Vorname darf nicht leer sein.")
        if not self.last_name:
            raise ValidationError("Nachname darf nicht leer sein.")
        if self.email and "@" not in self.email:
            raise ValidationError("Die E-Mail-Adresse ist ungültig.")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def has_id_document(self) -> bool:
        return self.id_document is not None and bool(self.id_document.number)


class RentalItem(ABC):
    """Gemeinsame Basisklasse aller Verleihgegenstände.

    Unterklassen legen ``type_key``, ``display_name`` und ihre
    ``attribute_fields`` fest und können eigene Preisregeln beisteuern.
    Die Basisklasse erledigt Validierung, Preisfeld und Serialisierung.
    """

    type_key: ClassVar[str] = ""
    display_name: ClassVar[str] = ""
    _fields: ClassVar[tuple[AttributeField, ...]] = ()

    def __init__(
        self,
        *,
        name: str,
        category: str,
        daily_rate: Decimal | str | float,
        attributes: dict[str, Any] | None = None,
        id: int | None = None,
        active: bool = True,
        created_at: datetime | None = None,
    ) -> None:
        self.id = id
        self.name = (name or "").strip()
        self.category = (category or "").strip()
        self.daily_rate = money(daily_rate)
        self.attributes: dict[str, Any] = dict(attributes or {})
        self.active = active
        self.created_at = created_at or datetime.now()
        self.validate()

    # ------------------------------------------------------------------
    # Validierung (Template-Method-Pattern)
    # ------------------------------------------------------------------
    def validate(self) -> None:
        if not self.name:
            raise ValidationError("Der Name des Gegenstands darf nicht leer sein.")
        if not self.category:
            raise ValidationError("Bitte eine Kategorie angeben.")
        if self.daily_rate <= 0:
            raise ValidationError("Der Tagespreis muss größer als 0 sein.")
        self._coerce_attributes()
        self.validate_attributes()

    def _coerce_attributes(self) -> None:
        """Typprüfung und Normalisierung der typspezifischen Attribute."""
        fields = {f.name: f for f in self.attribute_fields()}
        cleaned: dict[str, Any] = {}

        for key in list(self.attributes):
            if key not in fields:
                # Unbekannte Attribute verwerfen – verhindert Datenmüll aus alten Clients.
                self.attributes.pop(key)

        for name, spec in fields.items():
            value = self.attributes.get(name)
            if value is None or value == "":
                if spec.required:
                    raise ValidationError(f"'{spec.label}' ist ein Pflichtfeld.")
                continue

            if spec.kind == "number":
                try:
                    number = float(value)
                except (TypeError, ValueError) as exc:
                    raise ValidationError(f"'{spec.label}' muss eine Zahl sein.") from exc
                if number <= 0:
                    raise ValidationError(f"'{spec.label}' muss größer als 0 sein.")
                cleaned[name] = int(number) if number.is_integer() else number
            elif spec.kind == "bool":
                cleaned[name] = value if isinstance(value, bool) else str(value).lower() in {
                    "true",
                    "1",
                    "ja",
                    "yes",
                }
            elif spec.kind == "select":
                if spec.options and value not in spec.options:
                    raise ValidationError(
                        f"'{value}' ist für '{spec.label}' kein gültiger Wert."
                    )
                cleaned[name] = str(value)
            else:
                cleaned[name] = str(value).strip()

        self.attributes = cleaned

    def validate_attributes(self) -> None:
        """Hook für typspezifische Zusatzprüfungen."""

    # ------------------------------------------------------------------
    # Erweiterungspunkte
    # ------------------------------------------------------------------
    @classmethod
    def attribute_fields(cls) -> tuple[AttributeField, ...]:
        return cls._fields

    def pricing_rules(self) -> "Sequence[PricingRule]":
        """Objektabhängige Preisregeln, z. B. Aufpreis für Service."""
        return ()

    # ------------------------------------------------------------------
    # Darstellung
    # ------------------------------------------------------------------
    def describe(self) -> str:
        parts = []
        for spec in self.attribute_fields():
            value = self.attributes.get(spec.name)
            if value in (None, ""):
                continue
            if spec.kind == "bool":
                value = "ja" if value else "nein"
            parts.append(f"{spec.label}: {value}{spec.unit}")
        return ", ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "type_key": self.type_key,
            "type_label": self.display_name,
            "daily_rate": str(self.daily_rate),
            "attributes": dict(self.attributes),
            "description": self.describe(),
            "active": self.active,
            "created_at": self.created_at.isoformat(timespec="seconds"),
        }

    def __repr__(self) -> str:  # pragma: no cover - Debug-Ausgabe
        return f"<{type(self).__name__} {self.name!r} {self.daily_rate}>"


@dataclass
class Rental:
    """Ein Verleihvorgang."""

    item_id: int
    customer_id: int
    start_date: date
    days: int
    daily_rate: Decimal
    total: Decimal
    price_lines: list[dict[str, Any]] = field(default_factory=list)
    id: int | None = None
    created_at: datetime = field(default_factory=datetime.now)
    returned_at: datetime | None = None
    item_name: str = ""
    item_type: str = ""
    customer_name: str = ""

    @property
    def due_date(self) -> date:
        return self.start_date + timedelta(days=self.days)

    @property
    def is_returned(self) -> bool:
        return self.returned_at is not None

    def is_overdue(self, today: date | None = None) -> bool:
        return not self.is_returned and (today or date.today()) > self.due_date

    def days_until_due(self, today: date | None = None) -> int:
        return (self.due_date - (today or date.today())).days

    @property
    def status(self) -> str:
        if self.is_returned:
            return "returned"
        return "overdue" if self.is_overdue() else "active"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "item_id": self.item_id,
            "item_name": self.item_name,
            "item_type": self.item_type,
            "customer_id": self.customer_id,
            "customer_name": self.customer_name,
            "start_date": self.start_date.isoformat(),
            "due_date": self.due_date.isoformat(),
            "days": self.days,
            "daily_rate": str(self.daily_rate),
            "total": str(self.total),
            "price_lines": self.price_lines,
            "status": self.status,
            "days_until_due": self.days_until_due(),
            "returned_at": self.returned_at.isoformat(timespec="seconds")
            if self.returned_at
            else None,
            "created_at": self.created_at.isoformat(timespec="seconds"),
        }
