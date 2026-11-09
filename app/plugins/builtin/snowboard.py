"""Snowboard-Verleih – zweites Beispiel für einen weiteren Verleihtyp."""

from __future__ import annotations

from typing import Sequence

from ...domain.models import AttributeField, RentalItem
from ..api import RentalPlugin


class Snowboard(RentalItem):
    type_key = "snowboard"
    display_name = "Snowboard"
    _fields = (
        AttributeField("length_cm", "Länge", "number", required=True, unit=" cm"),
        AttributeField("stance", "Stand", "select", options=("Regular", "Goofy")),
        AttributeField("boots_included", "Boots inklusive", "bool"),
    )


class SnowboardPlugin(RentalPlugin):
    key = "snowboard"
    name = "Snowboard-Verleih"
    description = "Snowboards mit Länge, Stand und optionalem Boot-Verleih."

    def rental_item_types(self) -> Sequence[type[RentalItem]]:
        return (Snowboard,)


PLUGIN = SnowboardPlugin()
