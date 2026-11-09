"""Zentrale Konfiguration.

Alle Pfade lassen sich über Umgebungsvariablen überschreiben, damit die
Anwendung identisch auf Windows, Linux und im Test laufen kann.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _default_data_dir() -> Path:
    return PROJECT_ROOT / "data"


@dataclass(frozen=True)
class Settings:
    """Unveränderliche Konfiguration der Anwendung."""

    database_path: Path
    upload_dir: Path
    plugin_paths: tuple[Path, ...] = field(default_factory=tuple)
    currency: str = "EUR"

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = Path(os.getenv("RENTAL_DATA_DIR", _default_data_dir()))
        database_path = Path(os.getenv("RENTAL_DB_PATH", data_dir / "rental.db"))
        upload_dir = Path(os.getenv("RENTAL_UPLOAD_DIR", data_dir / "uploads"))
        raw_plugins = os.getenv("RENTAL_PLUGIN_PATHS", "")
        plugin_paths = tuple(
            Path(part.strip()) for part in raw_plugins.split(os.pathsep) if part.strip()
        )
        return cls(
            database_path=database_path,
            upload_dir=upload_dir,
            plugin_paths=plugin_paths,
            currency=os.getenv("RENTAL_CURRENCY", "EUR"),
        )

    def ensure_directories(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
