"""Plugin-Schnittstelle und Registry.

Ein Plugin bündelt alles, was eine neue Verleihart mitbringt:

* eine oder mehrere Unterklassen von :class:`RentalItem`,
* optionale Preisregeln,
* optionale Ausweistypen.

Der Rest des Systems kennt nur die Abstraktionen. Neue Verleiharten werden
dadurch ausschließlich durch Hinzufügen eines Plugins ergänzt – bestehender
Code bleibt unverändert (Open-Closed-Prinzip).
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from typing import Any, Callable, ClassVar, Sequence

from ..domain.errors import PluginError, ValidationError
from ..domain.models import RentalItem
from ..pricing.base import PricingRule


@dataclass(frozen=True)
class IdDocumentType:
    """Ein unterstützter Ausweistyp."""

    key: str
    label: str
    requires_number: bool = True
    allows_upload: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "requires_number": self.requires_number,
            "allows_upload": self.allows_upload,
        }


class RentalPlugin(ABC):
    """Basisklasse für Verleih-Plugins."""

    key: ClassVar[str] = ""
    name: ClassVar[str] = ""
    description: ClassVar[str] = ""

    def rental_item_types(self) -> Sequence[type[RentalItem]]:
        return ()

    def pricing_rules(self) -> Sequence[PricingRule]:
        return ()

    def id_document_types(self) -> Sequence[IdDocumentType]:
        return ()

    def describe(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "description": self.description,
            "item_types": [
                {"type_key": item_type.type_key, "label": item_type.display_name}
                for item_type in self.rental_item_types()
            ],
            "pricing_rules": [rule.key for rule in self.pricing_rules()],
            "id_document_types": [doc.key for doc in self.id_document_types()],
            "source": type(self).__module__,
        }


class PluginRegistry:
    """Sammelt alle Plugins und stellt ihre Beiträge bereit."""

    def __init__(self) -> None:
        self._plugins: dict[str, RentalPlugin] = {}
        self._item_types: dict[str, type[RentalItem]] = {}
        self._pricing_rules: dict[str, PricingRule] = {}
        self._id_document_types: dict[str, IdDocumentType] = {}
        self._listeners: list[Callable[[RentalPlugin], None]] = []

    def add_listener(self, callback: Callable[[RentalPlugin], None]) -> None:
        """Benachrichtigt ``callback`` über jedes neu registrierte Plugin.

        Damit kann der Preisdienst Preisregeln auch dann übernehmen, wenn ein
        Plugin erst zur Laufzeit registriert wird.
        """
        self._listeners.append(callback)

    # ------------------------------------------------------------------
    def register(self, plugin: RentalPlugin) -> None:
        if not plugin.key:
            raise PluginError(f"Plugin {type(plugin).__name__} hat keinen key.")
        if plugin.key in self._plugins:
            raise PluginError(f"Plugin '{plugin.key}' ist bereits registriert.")

        item_types = plugin.rental_item_types()
        rules = plugin.pricing_rules()

        # Erst prüfen, dann übernehmen – kein halb registriertes Plugin.
        for item_type in item_types:
            if not item_type.type_key:
                raise PluginError(f"Verleihtyp in Plugin '{plugin.key}' hat keinen type_key.")
            if item_type.type_key in self._item_types:
                raise PluginError(
                    f"Verleihtyp '{item_type.type_key}' ist bereits durch ein anderes Plugin belegt."
                )
        for rule in rules:
            if rule.key in self._pricing_rules:
                raise PluginError(f"Preisregel '{rule.key}' ist bereits registriert.")

        self._plugins[plugin.key] = plugin
        for item_type in item_types:
            self._item_types[item_type.type_key] = item_type
        for rule in rules:
            self._pricing_rules[rule.key] = rule
        for doc_type in plugin.id_document_types():
            self._id_document_types.setdefault(doc_type.key, doc_type)

        for listener in self._listeners:
            listener(plugin)

    # ------------------------------------------------------------------
    @property
    def plugins(self) -> tuple[RentalPlugin, ...]:
        return tuple(self._plugins.values())

    @property
    def item_types(self) -> dict[str, type[RentalItem]]:
        return dict(self._item_types)

    @property
    def pricing_rules(self) -> tuple[PricingRule, ...]:
        return tuple(self._pricing_rules.values())

    @property
    def id_document_types(self) -> dict[str, IdDocumentType]:
        return dict(self._id_document_types)

    def id_document_type(self, key: str) -> IdDocumentType:
        try:
            return self._id_document_types[key]
        except KeyError as exc:
            available = ", ".join(sorted(self._id_document_types)) or "keine"
            raise ValidationError(
                f"Unbekannter Ausweistyp '{key}'. Verfügbar: {available}."
            ) from exc

    def item_class(self, type_key: str) -> type[RentalItem]:
        try:
            return self._item_types[type_key]
        except KeyError as exc:
            available = ", ".join(sorted(self._item_types)) or "keine"
            raise ValidationError(
                f"Unbekannter Verleihtyp '{type_key}'. Verfügbar: {available}."
            ) from exc

    def build_item(self, type_key: str, **kwargs: Any) -> RentalItem:
        """Erzeugt einen Gegenstand des angegebenen Typs."""
        return self.item_class(type_key)(**kwargs)

    # ------------------------------------------------------------------
    def describe(self) -> dict[str, Any]:
        return {
            "plugins": [plugin.describe() for plugin in self._plugins.values()],
            "item_types": [
                {
                    "type_key": item_type.type_key,
                    "label": item_type.display_name,
                    "plugin": self._plugin_key_for_item_type(item_type.type_key),
                    "attributes": [spec.as_dict() for spec in item_type.attribute_fields()],
                }
                for item_type in self._item_types.values()
            ],
            "id_document_types": [doc.as_dict() for doc in self._id_document_types.values()],
            "pricing_rules": [rule.describe() for rule in self._pricing_rules.values()],
        }

    def _plugin_key_for_item_type(self, type_key: str) -> str:
        for plugin in self._plugins.values():
            if any(item.type_key == type_key for item in plugin.rental_item_types()):
                return plugin.key
        return ""
