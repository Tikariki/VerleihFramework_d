"""Beispiel-Plugin: Kajak-Verleih als externe Erweiterung.

So laden (ohne das Repository zu verändern):

    Windows:  $env:RENTAL_PLUGIN_PATHS = "examples\\plugins"; python run.py
    Linux:    RENTAL_PLUGIN_PATHS=examples/plugins python run.py

Danach erscheint "Kajak" im Dashboard unter Gegenstände > Gegenstand
anlegen > Verleihtyp.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from app.domain.models import AttributeField, RentalItem
from app.domain.money import percent_of
from app.pricing.base import PriceLine, PriceRequest, PricingRule, PriceState
from app.plugins.api import RentalPlugin


class Kayak(RentalItem):
    type_key = "kayak"
    display_name = "Kajak"
    _fields = (
        AttributeField("seats", "Sitzplätze", "number", required=True),
        AttributeField(
            "kind",
            "Art",
            "select",
            required=True,
            options=("Einer", "Zweier", "Familie"),
        ),
        AttributeField("spraydeck", "Spritzdecke inklusive", "bool"),
    )


class KayakInsuranceRule(PricingRule):
    """Kajaks werden nur mit Versicherung verliehen: 12 % Aufschlag."""

    key = "kayak_insurance"
    label = "Kajak-Versicherung"
    priority = 30
    PERCENT = Decimal("12")

    def applies(self, request: PriceRequest) -> bool:
        return request.item.type_key == "kayak"

    def apply(self, request: PriceRequest, state: PriceState) -> Sequence[PriceLine]:
        return [
            PriceLine(
                f"Versicherung Kajak (+{self.PERCENT:.0f} %)",
                percent_of(state.base, self.PERCENT),
            )
        ]

    def describe(self) -> dict:
        info = super().describe()
        info["source"] = "plugin:kayak"
        info["percent"] = str(self.PERCENT)
        return info


class KayakPlugin(RentalPlugin):
    key = "kayak"
    name = "Kajak-Verleih"
    description = "Kajaks mit Sitzplätzen, Art und Versicherungspflicht."

    def rental_item_types(self) -> Sequence[type[RentalItem]]:
        return (Kayak,)

    def pricing_rules(self) -> Sequence[PricingRule]:
        return (KayakInsuranceRule(),)


PLUGIN = KayakPlugin()
