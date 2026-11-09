"""Plugin-Loader.

Es gibt zwei Wege, ein Plugin ins System zu bringen:

1. **Eingebaut**: ein Modul unter ``app/plugins/builtin/``, das ein Objekt
   ``PLUGIN`` exportiert. Wird beim Start automatisch gefunden.
2. **Extern**: eine ``.py``-Datei in einem Verzeichnis, das über die
   Umgebungsvariable ``RENTAL_PLUGIN_PATHS`` (mehrere Pfade mit ``;`` bzw.
   ``:`` getrennt) angegeben wird. Ideal für Erweiterungen, die nicht im
   Repository liegen sollen.
"""

from __future__ import annotations

import importlib
import importlib.util
import pkgutil
import sys
from pathlib import Path
from typing import Iterator, Sequence

from ..domain.errors import PluginError
from .api import PluginRegistry, RentalPlugin

BUILTIN_PACKAGE = "app.plugins.builtin"


def load_plugins(extra_paths: Sequence[Path] = ()) -> PluginRegistry:
    """Baut eine Registry aus eingebauten und externen Plugins."""
    registry = PluginRegistry()
    for plugin in iter_builtin_plugins():
        registry.register(plugin)
    for path in extra_paths:
        for plugin in iter_external_plugins(Path(path)):
            registry.register(plugin)
    return registry


def iter_builtin_plugins() -> Iterator[RentalPlugin]:
    package = importlib.import_module(BUILTIN_PACKAGE)
    for module_info in pkgutil.iter_modules(package.__path__):
        if module_info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{BUILTIN_PACKAGE}.{module_info.name}")
        plugin = getattr(module, "PLUGIN", None)
        if plugin is not None:
            yield plugin


def iter_external_plugins(directory: Path) -> Iterator[RentalPlugin]:
    if not directory.exists():
        raise PluginError(f"Plugin-Verzeichnis '{directory}' existiert nicht.")
    if not directory.is_dir():
        raise PluginError(f"Plugin-Pfad '{directory}' ist kein Verzeichnis.")

    for file_path in sorted(directory.glob("*.py")):
        if file_path.name.startswith("_"):
            continue
        yield _load_plugin_file(file_path)


def _load_plugin_file(file_path: Path) -> RentalPlugin:
    module_name = f"rental_plugin_{file_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise PluginError(f"Plugin '{file_path}' konnte nicht geladen werden.")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # pragma: no cover - Fehlerfall
        raise PluginError(f"Fehler beim Laden von '{file_path.name}': {exc}") from exc

    plugin = getattr(module, "PLUGIN", None)
    if plugin is None:
        raise PluginError(f"Plugin '{file_path.name}' exportiert kein PLUGIN-Objekt.")
    return plugin
