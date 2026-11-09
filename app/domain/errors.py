"""Fachliche Fehlerklassen.

Jeder Fehler kennt seinen HTTP-Status, damit die API-Schicht keine
Fallunterscheidungen über Ausnahmetypen braucht.
"""

from __future__ import annotations


class DomainError(Exception):
    """Basisklasse aller fachlichen Fehler."""

    status_code = 400
    error_code = "domain_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ValidationError(DomainError):
    status_code = 422
    error_code = "validation_error"


class NotFoundError(DomainError):
    status_code = 404
    error_code = "not_found"


class ConflictError(DomainError):
    status_code = 409
    error_code = "conflict"


class ItemUnavailableError(ConflictError):
    error_code = "item_unavailable"


class PluginError(DomainError):
    status_code = 500
    error_code = "plugin_error"
