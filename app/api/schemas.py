"""Pydantic-Schemata der HTTP-Schnittstelle.

Sie beschreiben nur den Transport (JSON-Form), nicht die Fachlogik.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class ItemIn(BaseModel):
    type_key: str = Field(description="Verleihtyp aus der Plugin-Registry, z. B. 'ski'")
    name: str
    category: str = "Standard"
    daily_rate: Decimal = Field(gt=0, description="Tagespreis in Euro")
    attributes: dict[str, Any] = Field(default_factory=dict)


class ItemUpdate(BaseModel):
    type_key: str | None = None
    name: str | None = None
    category: str | None = None
    daily_rate: Decimal | None = Field(default=None, gt=0)
    attributes: dict[str, Any] | None = None
    active: bool | None = None


class CustomerIn(BaseModel):
    first_name: str
    last_name: str
    email: str = ""
    phone: str = ""
    id_type: str | None = None
    id_number: str | None = None


class CustomerUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    id_type: str | None = None
    id_number: str | None = None


class RentalIn(BaseModel):
    item_id: int
    customer_id: int
    days: int = Field(default=1, ge=1, le=365)
    start_date: str | None = Field(default=None, description="JJJJ-MM-TT, Standard: heute")


class RentalsFilter(BaseModel):
    status: str | None = None
    item_id: int | None = None
    customer_id: int | None = None
    limit: int | None = None


class MessageOut(BaseModel):
    message: str
    deleted: bool | None = None
    deactivated: bool | None = None
