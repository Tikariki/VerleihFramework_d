"""Tests des Plugin-Systems und der Erweiterbarkeit.

Der zentrale Nachweis: Ein neuer Verleihtyp wird ausschließlich durch ein
Plugin ergänzt, ohne dass bestehende Typen oder Preise sich verändern.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.domain.errors import PluginError, ValidationError
from app.domain.models import AttributeField, RentalItem
from app.plugins.api import RentalPlugin
from app.plugins.loader import load_plugins
from app.pricing.base import PriceLine, PriceRequest, PricingRule, PriceState
from app.pricing.service import PricingService


class Scooter(RentalItem):
    type_key = "scooter"
    display_name = "E-Scooter"
    _fields = (
        AttributeField("range_km", "Reichweite", "number", required=True, unit=" km"),
    )


class ScooterInsuranceRule(PricingRule):
    key = "scooter_insurance"
    label = "Versicherung E-Scooter"
    priority = 35
    FEE = Decimal("5.00")

    def applies(self, request: PriceRequest) -> bool:
        return request.item.type_key == "scooter"

    def apply(self, request: PriceRequest, state: PriceState):
        return [PriceLine("Versicherung (E-Scooter)", self.FEE)]


class ScooterPlugin(RentalPlugin):
    key = "scooter"
    name = "E-Scooter-Verleih"
    description = "Test-Plugin für die Erweiterbarkeit."

    def rental_item_types(self):
        return (Scooter,)

    def pricing_rules(self):
        return (ScooterInsuranceRule(),)


def _ski(registry, daily_rate: str = "25.00") -> RentalItem:
    return registry.build_item(
        "ski",
        name="Atomic Redster",
        category="Standard",
        daily_rate=daily_rate,
        attributes={"length_cm": 170},
    )


def test_eingebaute_plugins_stellen_verleiharten_bereit(registry):
    assert {"ski", "snowboard", "bike"} <= set(registry.item_types)
    assert registry.item_types["ski"].display_name == "Ski"


def test_ausweistypen_kommen_aus_einem_plugin(registry):
    types = registry.id_document_types
    assert types["id_card"].label == "Personalausweis"
    assert types["passport"].label == "Reisepass"


def test_neuer_verleihtyp_wird_registriert(registry):
    registry.register(ScooterPlugin())

    item = registry.build_item(
        "scooter",
        name="Xiaomi Pro 2",
        category="Standard",
        daily_rate="15.00",
        attributes={"range_km": 30},
    )

    assert item.type_key == "scooter"
    assert item.describe() == "Reichweite: 30 km"


def test_neuer_typ_veraendert_bestehende_ski_preise_nicht(registry):
    pricing_before = PricingService.with_defaults(registry.pricing_rules)
    ski = _ski(registry)
    total_before = pricing_before.quote(ski, days=4).total

    registry.register(ScooterPlugin())
    pricing_after = PricingService.with_defaults(registry.pricing_rules)
    total_after = pricing_after.quote(_ski(registry), days=4).total

    assert total_before == total_after == Decimal("90.00")


def test_plugin_preisregel_greift_nur_fuer_eigenen_typ(registry):
    registry.register(ScooterPlugin())
    pricing = PricingService.with_defaults(registry.pricing_rules)

    scooter = registry.build_item(
        "scooter",
        name="Xiaomi",
        category="Standard",
        daily_rate="15.00",
        attributes={"range_km": 30},
    )

    assert pricing.quote(scooter, days=1).total == Decimal("20.00")
    assert pricing.quote(_ski(registry), days=1).total == Decimal("25.00")


def test_verleih_eines_neuen_typs_ueber_die_services(container, make_customer, make_rental):
    container.registry.register(ScooterPlugin())
    item = container.items.create_item(
        {
            "type_key": "scooter",
            "name": "Xiaomi Pro 2",
            "category": "Standard",
            "daily_rate": "15.00",
            "attributes": {"range_km": 30},
        }
    )
    customer = make_customer()

    rental = make_rental(item.id, customer.id, start=date.today() + timedelta(days=5), days=1)

    assert rental.total == Decimal("20.00")
    assert rental.item_type == "scooter"


def test_doppelter_verleihtyp_wird_abgelehnt(registry):
    class FakeSki(RentalItem):
        type_key = "ski"
        display_name = "Fake-Ski"

    class DoppeltesPlugin(RentalPlugin):
        key = "fake_ski"
        name = "Doppeltes Plugin"

        def rental_item_types(self):
            return (FakeSki,)

    with pytest.raises(PluginError):
        registry.register(DoppeltesPlugin())


def test_doppelter_plugin_key_wird_abgelehnt(registry):
    registry.register(ScooterPlugin())

    with pytest.raises(PluginError):
        registry.register(ScooterPlugin())


def test_unbekannter_verleihtyp_wirft_validation_error(registry):
    with pytest.raises(ValidationError):
        registry.build_item(
            "hovercraft", name="X", category="Standard", daily_rate="10.00"
        )


def test_pflichtattribute_werden_validiert(registry):
    with pytest.raises(ValidationError):
        registry.build_item("ski", name="Ski", category="Standard", daily_rate="25.00")

    with pytest.raises(ValidationError):
        registry.build_item(
            "ski",
            name="Ski",
            category="Standard",
            daily_rate="25.00",
            attributes={"length_cm": "lang"},
        )


def test_externes_plugin_wird_aus_verzeichnis_geladen(tmp_path):
    plugin_code = '''
from app.domain.models import AttributeField, RentalItem
from app.plugins.api import RentalPlugin


class Segway(RentalItem):
    type_key = "segway"
    display_name = "Segway"
    _fields = (
        AttributeField("max_speed_kmh", "Hoechstgeschwindigkeit", "number",
                       required=True, unit=" km/h"),
    )


class SegwayPlugin(RentalPlugin):
    key = "segway"
    name = "Segway-Verleih"

    def rental_item_types(self):
        return (Segway,)


PLUGIN = SegwayPlugin()
'''
    (tmp_path / "segway.py").write_text(plugin_code, encoding="utf-8")

    registry = load_plugins([tmp_path])

    assert "segway" in registry.item_types
    assert "ski" in registry.item_types  # eingebaute Plugins bleiben erhalten
    item = registry.build_item(
        "segway",
        name="Ninebot",
        category="Standard",
        daily_rate="20.00",
        attributes={"max_speed_kmh": 20},
    )
    assert item.display_name == "Segway"


def test_externe_datei_ohne_plugin_objekt_wird_abgelehnt(tmp_path):
    (tmp_path / "kaputt.py").write_text("x = 1\n", encoding="utf-8")

    with pytest.raises(PluginError):
        load_plugins([tmp_path])


def test_metadaten_fuer_die_oberflaeche(registry):
    meta = registry.describe()

    assert len(meta["plugins"]) >= 4
    assert any(entry["type_key"] == "bike" for entry in meta["item_types"])
    assert any(rule["key"] == "bike_ebike_surcharge" for rule in meta["pricing_rules"])
