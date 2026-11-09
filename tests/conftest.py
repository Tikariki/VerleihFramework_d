"""Gemeinsame Fixtures für alle Tests."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.container import Container, build_container
from app.main import create_app
from app.plugins.api import PluginRegistry
from app.plugins.loader import load_plugins


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        database_path=tmp_path / "test.db",
        upload_dir=tmp_path / "uploads",
        plugin_paths=(),
    )


@pytest.fixture
def app(settings):
    return create_app(settings)


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def container(app) -> Container:
    return app.state.container


@pytest.fixture
def registry() -> PluginRegistry:
    return load_plugins()


@pytest.fixture
def make_item(container):
    def _make(
        type_key: str = "ski",
        name: str = "Atomic Redster 170",
        category: str = "Standard",
        daily_rate: str | Decimal = "25.00",
        attributes: dict | None = None,
        **extra,
    ):
        payload = {
            "type_key": type_key,
            "name": name,
            "category": category,
            "daily_rate": daily_rate,
            "attributes": attributes if attributes is not None else {"length_cm": 170},
        }
        payload.update(extra)
        return container.items.create_item(payload)

    return _make


@pytest.fixture
def make_customer(container):
    def _make(
        first_name: str = "Anna",
        last_name: str = "Müller",
        with_document: bool = True,
        email: str = "",
    ):
        data = {"first_name": first_name, "last_name": last_name, "email": email}
        if with_document:
            data.update({"id_type": "id_card", "id_number": "AT-123456789"})
        return container.customers.create_customer(data)

    return _make


@pytest.fixture
def make_rental(container):
    def _make(item_id: int, customer_id: int, start: date | None = None, days: int = 1):
        return container.rentals.create_rental(
            {
                "item_id": item_id,
                "customer_id": customer_id,
                "start_date": (start or date(2026, 1, 5)).isoformat(),
                "days": days,
            }
        )

    return _make


@pytest.fixture
def today() -> date:
    return date.today()


@pytest.fixture
def next_week() -> date:
    return date.today() + timedelta(days=7)
