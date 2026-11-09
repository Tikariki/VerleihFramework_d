"""Composition Root.

Einziger Ort, an dem konkrete Implementierungen zusammengesteckt werden.
Alle anderen Module kennen nur Abstraktionen bzw. ihre Nachbarn.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import Settings
from .plugins.api import PluginRegistry
from .plugins.loader import load_plugins
from .pricing.service import PricingService
from .repositories.database import Database
from .repositories.sqlite import CustomerRepository, ItemRepository, RentalRepository
from .services.customers import CustomerService
from .services.dashboard import DashboardService
from .services.items import ItemService
from .services.rentals import RentalService


@dataclass
class Container:
    settings: Settings
    database: Database
    registry: PluginRegistry
    pricing: PricingService
    items: ItemService
    customers: CustomerService
    rentals: RentalService
    dashboard: DashboardService


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or Settings.from_env()
    settings.ensure_directories()

    database = Database(settings.database_path)
    database.initialize()

    registry = load_plugins(settings.plugin_paths)
    pricing = PricingService.with_defaults()

    # Preisregeln bestehender Plugins übernehmen und für später registrierte
    # Plugins automatisch nachziehen.
    registry.add_listener(lambda plugin: _register_plugin_rules(pricing, plugin))
    for rule in registry.pricing_rules:
        pricing.register(rule)

    item_repo = ItemRepository(database, registry)
    customer_repo = CustomerRepository(database)
    rental_repo = RentalRepository(database)

    return Container(
        settings=settings,
        database=database,
        registry=registry,
        pricing=pricing,
        items=ItemService(item_repo, rental_repo, registry),
        customers=CustomerService(customer_repo, rental_repo, registry),
        rentals=RentalService(rental_repo, item_repo, customer_repo, pricing),
        dashboard=DashboardService(item_repo, customer_repo, rental_repo, registry, pricing),
    )


def _register_plugin_rules(pricing: PricingService, plugin) -> None:
    """Übernimmt die Preisregeln eines Plugins in den Preisdienst."""
    for rule in plugin.pricing_rules():
        pricing.register(rule)
