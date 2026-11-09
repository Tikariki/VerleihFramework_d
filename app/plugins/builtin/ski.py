"""Ski-Verleih – das Referenz-Plugin des Systems."""

from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from ...domain.models import AttributeField, RentalItem
from ...pricing.base import PriceLine, PriceRequest, PricingRule, PriceState
from ..api import RentalPlugin


class SkiServiceFeeRule(PricingRule):
    """Service-Paket (Wachsen, Kantenschliff) als objektabhängige Regel."""

    key = "ski_service_fee"
    label = "Service-Paket Ski"
    priority = 30
    FEE = Decimal("14.90")

    def applies(self, request: PriceRequest) -> bool:
        return bool(request.item.attributes.get("service_package"))

    def apply(self, request: PriceRequest, state: PriceState) -> Sequence[PriceLine]:
        return [PriceLine("Service-Paket (Wachsen & Kantenschliff)", self.FEE)]

    def describe(self) -> dict:
        info = super().describe()
        info["source"] = "plugin:ski"
        info["fee"] = str(self.FEE)
        return info


class Ski(RentalItem):
    type_key = "ski"
    display_name = "Ski"
    _fields = (
        AttributeField("length_cm", "Länge", "number", required=True, unit=" cm"),
        AttributeField(
            "skill_level",
            "Fahrkönnen",
            "select",
            options=("Anfänger", "Fortgeschritten", "Profi"),
        ),
        AttributeField("service_package", "Service-Paket", "bool"),
    )

    def pricing_rules(self) -> Sequence[PricingRule]:
        if self.attributes.get("service_package"):
            return (SkiServiceFeeRule(),)
        return ()


class SkiPlugin(RentalPlugin):
    key = "ski"
    name = "Ski-Verleih"
    description = "Ski mit Länge, Fahrkönnen und optionalem Service-Paket."

    def rental_item_types(self) -> Sequence[type[RentalItem]]:
        return (Ski,)

    def pricing_rules(self) -> Sequence[PricingRule]:
        return (SkiServiceFeeRule(),)


PLUGIN = SkiPlugin()
