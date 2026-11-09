"""Geldrechnung.

Geldbeträge werden intern als ``Decimal`` mit zwei Nachkommastellen geführt
und in der Datenbank als ganzzahlige Cent gespeichert. Fließkomma-Rundungs-
fehler sind damit ausgeschlossen.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")


def money(value: Decimal | str | int | float) -> Decimal:
    """Wandelt einen beliebigen Betrag in einen gerundeten Geldwert."""
    if isinstance(value, Decimal):
        amount = value
    elif isinstance(value, int):
        amount = Decimal(value)
    else:
        amount = Decimal(str(value))
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def to_cents(value: Decimal | str | int | float) -> int:
    """Geldwert als ganzzahlige Cent (für die Persistenz)."""
    return int((money(value) * 100).to_integral_value(rounding=ROUND_HALF_UP))


def from_cents(cents: int) -> Decimal:
    """Cent zurück in einen Geldwert."""
    return money(Decimal(cents) / 100)


def percent_of(base: Decimal, percent: Decimal) -> Decimal:
    """Prozentualer Anteil eines Betrags, kaufmännisch gerundet."""
    return money(base * Decimal(percent) / Decimal(100))
