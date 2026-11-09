"""Kern-Preisregeln des Verleihsystems."""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Sequence

from ..domain.money import money, percent_of
from .base import PriceLine, PriceRequest, PricingRule, PriceState


class DurationRateRule(PricingRule):
    """Grundpreis aus Tagespreis × Verleihdauer, mit Mengenrabatt.

    Die Rabattstaffel ist konfigurierbar und kann zur Laufzeit ersetzt
    werden, ohne die Architektur zu ändern.
    """

    key = "duration"
    label = "Tagespreis mit Mengenrabatt"
    priority = 10

    DEFAULT_TIERS: Sequence[tuple[int, Decimal]] = (
        (7, Decimal("20")),
        (4, Decimal("10")),
        (1, Decimal("0")),
    )

    def __init__(self, tiers: Sequence[tuple[int, Decimal]] | None = None) -> None:
        self._tiers = sorted(tiers or self.DEFAULT_TIERS, key=lambda tier: tier[0], reverse=True)

    def discount_percent(self, days: int) -> Decimal:
        for min_days, percent in self._tiers:
            if days >= min_days:
                return Decimal(percent)
        return Decimal("0")

    def apply(self, request: PriceRequest, state: PriceState) -> Iterable[PriceLine]:
        rate = request.item.daily_rate
        gross = money(rate * request.days)
        discount_percent = self.discount_percent(request.days)

        lines = [
            PriceLine(
                f"{request.days} Tag(e) à {rate} {_currency()}",
                gross,
            )
        ]

        if discount_percent > 0:
            discount = percent_of(gross, discount_percent)
            lines.append(
                PriceLine(f"Langzeitrabatt ({_fmt_percent(discount_percent)})", -discount)
            )
            state.base = money(gross - discount)
        else:
            state.base = gross

        return lines

    def describe(self) -> dict:
        info = super().describe()
        info["tiers"] = [
            {"min_days": days, "discount_percent": str(percent)} for days, percent in self._tiers
        ]
        return info


class CategorySurchargeRule(PricingRule):
    """Aufschlag oder Rabatt abhängig von der Kategorie des Gegenstands.

    Beispiel: Premium-Ski kosten 15 % mehr, Kinderausrüstung 10 % weniger.
    Die Zuordnung ist reine Konfiguration.
    """

    key = "category"
    label = "Kategorieabhängiger Aufschlag"
    priority = 40

    DEFAULT_MAPPING: dict[str, Decimal] = {
        "Premium": Decimal("15"),
        "Kinder": Decimal("-10"),
    }

    def __init__(self, mapping: dict[str, Decimal] | None = None) -> None:
        self._mapping = {
            category: Decimal(str(percent))
            for category, percent in (mapping or self.DEFAULT_MAPPING).items()
        }

    def applies(self, request: PriceRequest) -> bool:
        percent = self._mapping.get(request.item.category, Decimal("0"))
        return percent != 0

    def apply(self, request: PriceRequest, state: PriceState) -> Iterable[PriceLine]:
        percent = self._mapping.get(request.item.category, Decimal("0"))
        amount = percent_of(state.base, percent)
        if percent > 0:
            label = f"Kategorie {request.item.category} (+{_fmt_percent(percent)})"
        else:
            label = f"Kategorie {request.item.category} ({_fmt_percent(percent)})"
        line = PriceLine(label, amount)
        return [line]

    def describe(self) -> dict:
        info = super().describe()
        info["categories"] = {k: str(v) for k, v in self._mapping.items()}
        return info


def _currency() -> str:
    return "€"


def _fmt_percent(percent: Decimal) -> str:
    value = f"{Decimal(percent):.0f}"
    return f"{value} %"
