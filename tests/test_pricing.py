"""Tests der Preisberechnung."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.domain.errors import ValidationError
from app.pricing.base import PriceLine, PriceRequest, PricingRule, PriceState
from app.pricing.rules import CategorySurchargeRule, DurationRateRule
from app.pricing.service import PricingService


@pytest.fixture
def pricing(registry):
    return PricingService.with_defaults(registry.pricing_rules)


def test_ein_tag_ohne_rabatt(pricing, make_item):
    item = make_item(daily_rate="25.00")
    quote = pricing.quote(item, days=1, start_date=date(2026, 1, 5))
    assert quote.total == Decimal("25.00")
    assert len(quote.lines) == 1


def test_drei_tage_ohne_rabatt(pricing, make_item):
    quote = pricing.quote(make_item(daily_rate="25.00"), days=3)
    assert quote.total == Decimal("75.00")


def test_vier_tage_zehn_prozent_rabatt(pricing, make_item):
    quote = pricing.quote(make_item(daily_rate="25.00"), days=4)
    # 4 × 25 = 100, minus 10 % = 90
    assert quote.total == Decimal("90.00")


def test_sieben_tage_zwanzig_prozent_rabatt(pricing, make_item):
    quote = pricing.quote(make_item(daily_rate="25.00"), days=7)
    # 7 × 25 = 175, minus 20 % = 140
    assert quote.total == Decimal("140.00")


def test_rabattstaffel_ist_konfigurierbar(make_item):
    rule = DurationRateRule(tiers=[(3, Decimal("50"))])
    pricing = PricingService(rules=[rule])
    quote = pricing.quote(make_item(daily_rate="10.00"), days=3)
    assert quote.total == Decimal("15.00")


def test_premium_kategorie_aufschlag(pricing, make_item):
    item = make_item(daily_rate="20.00", category="Premium")
    quote = pricing.quote(item, days=2)
    # 40 + 15 % = 46
    assert quote.total == Decimal("46.00")


def test_kinder_kategorie_rabatt(pricing, make_item):
    item = make_item(daily_rate="20.00", category="Kinder")
    quote = pricing.quote(item, days=2)
    assert quote.total == Decimal("36.00")


def test_kategorie_aufschlag_rechnet_auf_rabattierten_preis(pricing, make_item):
    item = make_item(daily_rate="10.00", category="Premium")
    quote = pricing.quote(item, days=7)
    # 70 − 20 % = 56, plus 15 % = 64.40
    assert quote.total == Decimal("64.40")


def test_service_paket_ski_ist_objektabhaengig(pricing, make_item):
    item = make_item(attributes={"length_cm": 170, "service_package": True})
    quote = pricing.quote(item, days=1)
    labels = [line.label for line in quote.lines]
    assert any("Service-Paket" in label for label in labels)
    assert quote.total == Decimal("39.90")


def test_service_paket_nur_bei_ski(pricing, make_item):
    item = make_item(
        type_key="bike",
        attributes={"bike_kind": "City", "frame_size": "M"},
    )
    quote = pricing.quote(item, days=1)
    assert all("Service-Paket" not in line.label for line in quote.lines)


def test_ebike_aufschlag(pricing, make_item):
    item = make_item(
        type_key="bike",
        daily_rate="20.00",
        attributes={"bike_kind": "E-Bike", "frame_size": "L"},
    )
    quote = pricing.quote(item, days=2)
    # 40 + 20 % = 48
    assert quote.total == Decimal("48.00")


def test_mountainbike_ohne_aufschlag(pricing, make_item):
    item = make_item(
        type_key="bike",
        daily_rate="20.00",
        attributes={"bike_kind": "Mountain", "frame_size": "L"},
    )
    quote = pricing.quote(item, days=2)
    assert quote.total == Decimal("40.00")


def test_ungueltige_dauer_wird_abgelehnt(pricing, make_item):
    item = make_item()
    with pytest.raises(ValidationError):
        pricing.quote(item, days=0)
    with pytest.raises(ValidationError):
        pricing.quote(item, days=400)


def test_neue_regel_laesst_sich_ohne_kernänderung_ergaenzen(pricing, make_item):
    class WinterSurcharge(PricingRule):
        key = "winter_surcharge"
        label = "Wintersaison"
        priority = 50

        def applies(self, request: PriceRequest) -> bool:
            return request.start_date.month in (12, 1, 2)

        def apply(self, request: PriceRequest, state: PriceState):
            return [PriceLine("Wintersaison (+10 %)", (state.base * Decimal("0.10")).quantize(Decimal("0.01")))]

    pricing.register(WinterSurcharge())
    winter = pricing.quote(make_item(daily_rate="10.00"), days=1, start_date=date(2026, 1, 5))
    summer = pricing.quote(make_item(daily_rate="10.00"), days=1, start_date=date(2026, 7, 5))
    assert winter.total == Decimal("11.00")
    assert summer.total == Decimal("10.00")


def test_regeln_werden_nach_prioritaet_ausgefuehrt(registry):
    pricing = PricingService.with_defaults(registry.pricing_rules)
    priorities = [rule.priority for rule in pricing.rules]
    assert priorities == sorted(priorities)
    assert isinstance(pricing.rules[0], DurationRateRule)


def test_reihenfolge_dauer_vor_kategorie():
    pricing = PricingService(rules=[CategorySurchargeRule(), DurationRateRule()])
    assert [rule.key for rule in pricing.rules] == ["duration", "category"]
