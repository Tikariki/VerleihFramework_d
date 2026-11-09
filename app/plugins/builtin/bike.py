"""Fahrrad-Verleih.

Dieses Plugin ist der Beweis, dass die Architektur nicht ski-spezifisch ist:
Es nutzt dieselbe Basisklasse, dieselbe Registry und dieselbe Preis-Pipeline
wie Ski – ohne eine Zeile im Kern zu ändern.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from ...domain.models import AttributeField, RentalItem
from ...domain.money import percent_of
from ...pricing.base import PriceLine, PriceRequest, PricingRule, PriceState
from ..api import RentalPlugin


class EbikeSurchargeRule(PricingRule):
    """E-Bikes kosten 20 % Aufschlag auf den Grundpreis."""

    key = "bike_ebike_surcharge"
    label = "E-Bike-Aufschlag"
    priority = 30
    PERCENT = Decimal("20")

    def applies(self, request: PriceRequest) -> bool:
        return (
            request.item.type_key == "bike"
            and request.item.attributes.get("bike_kind") == "E-Bike"
        )

    def apply(self, request: PriceRequest, state: PriceState) -> Sequence[PriceLine]:
        return [PriceLine(f"E-Bike-Aufschlag (+{self.PERCENT:.0f} %)", percent_of(state.base, self.PERCENT))]

    def describe(self) -> dict:
        info = super().describe()
        info["source"] = "plugin:bike"
        info["percent"] = str(self.PERCENT)
        return info


class Bike(RentalItem):
    type_key = "bike"
    display_name = "Fahrrad"
    _fields = (
        AttributeField(
            "bike_kind",
            "Radtyp",
            "select",
            required=True,
            options=("City", "Mountain", "Rennrad", "E-Bike"),
        ),
        AttributeField(
            "frame_size",
            "Rahmengröße",
            "select",
            required=True,
            options=("XS", "S", "M", "L", "XL"),
        ),
        AttributeField("helmet_included", "Helm inklusive", "bool"),
    )


class BikePlugin(RentalPlugin):
    key = "bike"
    name = "Fahrrad-Verleih"
    description = "Fahrräder inklusive E-Bike-Aufschlag."

    def rental_item_types(self) -> Sequence[type[RentalItem]]:
        return (Bike,)

    def pricing_rules(self) -> Sequence[PricingRule]:
        return (EbikeSurchargeRule(),)


PLUGIN = BikePlugin()
