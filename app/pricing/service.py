"""Zentrale Preisberechnung.

Der ``PricingService`` ist der einzige Ort, an dem Preise entstehen. Er führt
die registrierten Regeln in Prioritätsreihenfolge aus und setzt daraus die
Rechnung zusammen. Objekt- und pluginspezifische Regeln werden dabei
automatisch mit den Kernregeln kombiniert.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Iterable, Sequence

from ..domain.errors import ValidationError
from ..domain.models import Customer, RentalItem
from .base import PriceLine, PriceQuote, PriceRequest, PricingRule, PriceState
from .rules import CategorySurchargeRule, DurationRateRule


class PricingService:
    MIN_DAYS = 1
    MAX_DAYS = 365

    def __init__(
        self,
        rules: Iterable[PricingRule] | None = None,
        item_rules: Iterable[PricingRule] | None = None,
    ) -> None:
        self._rules: list[PricingRule] = []
        for rule in rules or ():
            self.register(rule)
        for rule in item_rules or ():
            self.register(rule)

    @classmethod
    def with_defaults(cls, extra_rules: Iterable[PricingRule] = ()) -> "PricingService":
        """Preisdienst mit Kernregeln plus den Regeln aus Plugins."""
        return cls([DurationRateRule(), CategorySurchargeRule(), *extra_rules])

    # ------------------------------------------------------------------
    def register(self, rule: PricingRule) -> None:
        """Registriert eine Regel; gleiche ``key`` ersetzt die alte Regel."""
        self._rules = [existing for existing in self._rules if existing.key != rule.key]
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority)

    @property
    def rules(self) -> tuple[PricingRule, ...]:
        return tuple(self._rules)

    def describe(self) -> list[dict]:
        return [rule.describe() for rule in self._rules]

    # ------------------------------------------------------------------
    def quote(
        self,
        item: RentalItem,
        days: int,
        start_date: date | None = None,
        customer: Customer | None = None,
    ) -> PriceQuote:
        days = self._validate_days(days)
        request = PriceRequest(
            item=item,
            days=days,
            start_date=start_date or date.today(),
            customer=customer,
        )

        state = PriceState(request=request)
        for rule in self._rules_for(item):
            if not rule.applies(request):
                continue
            for line in rule.apply(request, state):
                state.add(line)

        if not state.lines:
            raise ValidationError("Für diesen Gegenstand ist keine Preisregel definiert.")

        return PriceQuote(
            item_id=item.id,
            item_name=item.name,
            days=days,
            daily_rate=item.daily_rate,
            lines=tuple(state.lines),
            total=state.total,
        )

    def _rules_for(self, item: RentalItem) -> Sequence[PricingRule]:
        """Kernregeln + objektabhängige Regeln, dedupliziert über ``key``."""
        merged: dict[str, PricingRule] = {rule.key: rule for rule in self._rules}
        for rule in item.pricing_rules():
            merged[rule.key] = rule
        return sorted(merged.values(), key=lambda r: r.priority)

    def _validate_days(self, days: int) -> int:
        try:
            days = int(days)
        except (TypeError, ValueError) as exc:
            raise ValidationError("Die Verleihdauer muss eine ganze Zahl sein.") from exc
        if days < self.MIN_DAYS:
            raise ValidationError("Die Verleihdauer muss mindestens 1 Tag betragen.")
        if days > self.MAX_DAYS:
            raise ValidationError(f"Die Verleihdauer darf höchstens {self.MAX_DAYS} Tage betragen.")
        return days


def sum_lines(lines: Iterable[PriceLine]) -> Decimal:
    """Hilfsfunktion: Summe von Prespositionen (für Tests und Reports)."""
    return sum((line.amount for line in lines), Decimal("0.00"))
