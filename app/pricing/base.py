"""Bausteine der Preisberechnung.

Eine Preisregel bekommt eine ``PriceRequest`` (was wird wie lange verliehen?)
und den bisherigen ``PriceState`` und liefert null oder mehr Prespositionen.
Neue Regeln – auch aus Plugins – erben von ``PricingRule`` und werden über
ihre ``priority`` in die Kette einsortiert.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, ClassVar, Iterable, TYPE_CHECKING

from ..domain.money import money

if TYPE_CHECKING:  # pragma: no cover
    from ..domain.models import Customer, RentalItem


@dataclass(frozen=True)
class PriceRequest:
    """Eingabe einer Preisberechnung."""

    item: "RentalItem"
    days: int
    start_date: date
    customer: "Customer | None" = None


@dataclass(frozen=True)
class PriceLine:
    """Eine Position auf der Rechnung."""

    label: str
    amount: Decimal

    def as_dict(self) -> dict[str, str]:
        return {"label": self.label, "amount": str(self.amount)}


@dataclass
class PriceState:
    """Laufender Zustand während der Regelkette."""

    request: PriceRequest
    base: Decimal = Decimal("0.00")
    lines: list[PriceLine] = field(default_factory=list)

    def add(self, line: PriceLine) -> None:
        self.lines.append(PriceLine(line.label, money(line.amount)))

    @property
    def total(self) -> Decimal:
        return money(sum((line.amount for line in self.lines), Decimal("0.00")))


class PricingRule(ABC):
    """Basisklasse aller Preisregeln."""

    key: ClassVar[str] = ""
    label: ClassVar[str] = ""
    priority: ClassVar[int] = 100

    def applies(self, request: PriceRequest) -> bool:
        """Vorprüfung; Standard: Regel gilt immer."""
        return True

    @abstractmethod
    def apply(self, request: PriceRequest, state: PriceState) -> Iterable[PriceLine]:
        """Liefert die Prespositionen dieser Regel."""

    def describe(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "priority": self.priority,
            "source": "core",
        }


@dataclass(frozen=True)
class PriceQuote:
    """Ergebnis einer Preisberechnung."""

    item_id: int | None
    item_name: str
    days: int
    daily_rate: Decimal
    lines: tuple[PriceLine, ...]
    total: Decimal

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "item_name": self.item_name,
            "days": self.days,
            "daily_rate": str(self.daily_rate),
            "lines": [line.as_dict() for line in self.lines],
            "total": str(self.total),
        }
