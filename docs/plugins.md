# Plugin-System

Das Plugin-System ist die zentrale Erweiterungsstelle des Systems. Alles, was
fachlich neu ist – ein Verleihgegenstand, eine Preisregel, ein Ausweistyp –
kommt als Plugin hinzu. Der Kern wird dabei nicht verändert.

## Was ein Plugin beisteuern kann

| Beitrag | Methode | Wirkung |
|---|---|---|
| Verleiharten | `rental_item_types()` | neue Unterklassen von `RentalItem`, erscheinen in API und Dashboard |
| Preisregeln | `pricing_rules()` | werden in die Preis-Pipeline einsortiert |
| Ausweistypen | `id_document_types()` | erlaubte Werte für `id_type` bei Kunden |

Ein Plugin darf nur einen dieser Beiträge liefern; das Identitäts-Plugin
beispielsweise liefert ausschließlich Ausweistypen.

## Schnittstelle

```python
class RentalPlugin(ABC):
    key: ClassVar[str]        # eindeutig, z. B. "ski"
    name: ClassVar[str]       # Anzeigename, z. B. "Ski-Verleih"
    description: ClassVar[str] = ""

    def rental_item_types(self) -> Sequence[type[RentalItem]]: ...
    def pricing_rules(self) -> Sequence[PricingRule]: ...
    def id_document_types(self) -> Sequence[IdDocumentType]: ...
```

Ein Modul wird nur dann als Plugin erkannt, wenn es ein Objekt `PLUGIN`
exportiert:

```python
PLUGIN = SkiPlugin()
```

## Registry

`PluginRegistry` sammelt die Beiträge und stellt sie dem Rest des Systems
bereit.

| Element | Bedeutung |
|---|---|
| `register(plugin)` | prüft auf Duplikate und übernimmt das Plugin |
| `add_listener(callback)` | Callback bei jeder Registrierung (der Preisdienst hängt sich daran) |
| `item_types` | `type_key -> Klasse` |
| `item_class(type_key)` / `build_item(type_key, **kwargs)` | Typ auflösen bzw. Gegenstand erzeugen |
| `pricing_rules` | alle Regeln aus Plugins |
| `id_document_types` / `id_document_type(key)` | Ausweistypen auflösen |
| `describe()` | Metadaten für `GET /api/meta` und das Dashboard |

Die Registry ist die einzige Stelle, die weiß, welche Verleiharten es gibt. Sie
prüft vor der Übernahme alle Beiträge; schlägt eine Prüfung fehl, wird das
Plugin vollständig abgelehnt (`PluginError`), damit kein halb registrierter
Zustand entsteht.

Typische Fehlerfälle:

- Plugin ohne `key`
- `key` bereits vergeben
- `type_key` bereits von einem anderen Plugin belegt
- Regel-`key` bereits vergeben
- Modul exportiert kein `PLUGIN`-Objekt
- Fehler beim Import der Plugin-Datei

## Laden

**Eingebaute Plugins** liegen in `app/plugins/builtin/`. Jedes Modul, das nicht
mit `_` beginnt und `PLUGIN` exportiert, wird beim Start automatisch geladen.
Vorhanden sind:

| Modul | Plugin-Key | Beitrag |
|---|---|---|
| `ski.py` | `ski` | Verleihtyp `Ski`, Service-Paket-Regel |
| `snowboard.py` | `snowboard` | Verleihtyp `Snowboard` |
| `bike.py` | `bike` | Verleihtyp `Fahrrad`, E-Bike-Aufschlag |
| `identity.py` | `identity` | Ausweistypen (Personalausweis, Reisepass, Führerschein, Studentenausweis) |

**Externe Plugins** liegen in beliebigen Verzeichnissen, die über die
Umgebungsvariable `RENTAL_PLUGIN_PATHS` bekannt gemacht werden:

```bash
# Linux / macOS
export RENTAL_PLUGIN_PATHS=/pfad/zu/plugins:/pfad/zu/weitere

# Windows (PowerShell)
$env:RENTAL_PLUGIN_PATHS = "C:\plugins;C:\plugins2"
python run.py
```

Jede `.py`-Datei in diesen Verzeichnissen wird importiert (Dateien mit
führendem `_` werden übersprungen) und muss `PLUGIN` exportieren. Der Vorteil:
Erweiterungen müssen nicht im Repository liegen.

## Zusammenspiel mit der Preisberechnung

`PricingService` bekommt beim Start die Kernregeln (`duration`, `category`) und
alle Regeln der Registry. Zusätzlich registriert der Container einen Listener,
der neue Plugin-Regeln sofort nachzieht:

```python
registry.add_listener(lambda plugin: _register_plugin_rules(pricing, plugin))
```

Regeln werden nach `priority` sortiert ausgeführt. Objektabhängige Regeln aus
`RentalItem.pricing_rules()` überschreiben eine Regel mit demselben `key`.

## Zusammenspiel mit dem Dashboard

Das Frontend kennt keine Verleiharten. Es ruft `GET /api/meta` auf und erhält:

```json
{
  "item_types": [
    {"type_key": "ski", "label": "Ski", "plugin": "ski",
     "attributes": [
       {"name": "length_cm", "label": "Länge", "kind": "number",
        "required": true, "unit": " cm"}
     ]}
  ],
  "id_document_types": [{"key": "id_card", "label": "Personalausweis"}],
  "pricing_rules": [{"key": "duration", "label": "...", "priority": 10}]
}
```

Daraus baut `app/static/app.js` die Formulare für neue Gegenstände. Ein neuer
Verleihtyp erscheint dadurch ohne Frontend-Änderung im Dropdown, in den
Eingabefeldern und in der Filterleiste.

## Testen von Plugins

`tests/test_plugins.py` zeigt das Muster:

1. Plugin-Klasse inline definieren (wie `ScooterPlugin` im Test).
2. `registry.register(...)` und prüfen, dass der Typ verfügbar ist.
3. Preis vor und nach der Registrierung vergleichen, um Regressionen bei
   bestehenden Typen auszuschließen.
4. Externe Datei über `load_plugins([tmp_path])` laden und prüfen, dass sowohl
   das externe als auch die eingebauten Plugins vorhanden sind.
