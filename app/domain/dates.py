"""Hilfsfunktionen für Datumswerte."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from .errors import ValidationError


def parse_iso_date(value: Any, field: str = "Datum") -> date | None:
    """Parst ``JJJJ-MM-TT`` (oder ein ``date``/``datetime``) zu einem Datum."""
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValidationError(f"'{field}': '{value}' ist kein gültiges Datum (JJJJ-MM-TT).") from exc
