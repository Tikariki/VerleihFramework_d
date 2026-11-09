# Anleitung: neuen Verleihtyp hinzufügen

Diese Anleitung führt einmal komplett durch, was nötig ist, um eine neue
Verleihart ins System zu bringen – am Beispiel Kajak. Das fertige Beispiel liegt
unter `examples/plugins/kayak.py` und lässt sich direkt starten.

**Was Sie nicht anfassen müssen:** Datenbankschema, API-Routen, Dashboard-Code,
Preislogik des Kerns. Ein Verleihtyp ist ein Plugin, sonst nichts.

## Schritt 1: Entscheiden, wo das Plugin lebt

| Fall | Ort |
|---|---|
| gehört fest zum Produkt | `app/plugins/builtin/<name>.py` |
| Erweiterung, die nicht im Repository liegen soll | beliebiges Verzeichnis, über `RENTAL_PLUGIN_PATHS` eingebunden |

Beide Wege sind technisch gleichwertig. Für den Einstieg ist `builtin/`
einfacher, weil kein Pfad gesetzt werden muss.

## Schritt 2: Gegenstandstyp definieren

Der Typ erbt von `RentalItem`. Pflicht sind `type_key` (eindeutig, technisch),
`display_name` (Anzeige) und die typspezifischen Felder.

```python
from app.domain.models import AttributeField, RentalItem


class Kayak(RentalItem):
    type_key = "kayak"
    display_name = "Kajak"
    _fields = (
        AttributeField("seats", "Sitzplätze", "number", required=True),
        AttributeField(
            "kind", "Art", "select", required=True,
            options=("Einer", "Zweier", "Familie"),
        ),
        AttributeField("spraydeck", "Spritzdecke inklusive", "bool"),
    )
```

Verfügbare Feldtypen (`kind`):

| `kind` | Eingabe im Dashboard | Validierung | Wert im `attributes`-Dict |
|---|---|---|---|
| `text` | Textfeld | Pflichtfeld, falls `required` | `str` |
| `number` | Zahlfeld | Pflichtfeld, muss > 0 sein | `int` oder `float` |
| `select` | Auswahlliste | Wert muss in `options` liegen | `str` |
| `bool` | Checkbox | – | `bool` |

`unit` wird nur als Platzhalter im Formular angezeigt (z. B. `" cm"`).
`name`, `category` und `daily_rate` bringt die Basisklasse mit; sie werden beim
Anlegen gepflegt und müssen nicht deklariert werden.

## Schritt 3: Plugin-Klasse anlegen

```python
from app.plugins.api import RentalPlugin


class KayakPlugin(RentalPlugin):
    key = "kayak"
    name = "Kajak-Verleih"
    description = "Kajaks mit Sitzplätzen, Art und Versicherungspflicht."

    def rental_item_types(self):
        return (Kayak,)


PLUGIN = KayakPlugin()
```

Ohne `PLUGIN` wird das Modul nicht als Plugin erkannt. Der `key` muss
repo-weit eindeutig sein, ebenso jeder `type_key`.

## Schritt 4 (optional): eigene Preisregel

Will die neue Verleihart eigene Preise, ergänzt man eine Regel. Sie darf nur für
den eigenen Typ greifen – sonst beeinflusst sie fremde Verleiharten.

```python
from decimal import Decimal
from app.domain.money import percent_of
from app.pricing.base import PriceLine, PriceRequest, PricingRule, PriceState


class KayakInsuranceRule(PricingRule):
    key = "kayak_insurance"
    label = "Kajak-Versicherung"
    priority = 30

    def applies(self, request: PriceRequest) -> bool:
        return request.item.type_key == "kayak"

    def apply(self, request: PriceRequest, state: PriceState):
        return [PriceLine("Versicherung Kajak (+12 %)", percent_of(state.base, Decimal("12")))]
```

`state.base` ist der Zwischenstand nach dem Grundpreis (inklusive
Langzeitrabatt). Prioritäten im System:

| Priorität | Bedeutung |
|---|---|
| 10 | Grundpreis (Tagespreis × Dauer, Staffelrabatt) |
| 20–30 | Zuschläge und Pauschalen, auch aus Plugins |
| 40 | Kategorie-Aufschlag |
| ab 50 | Sonderfälle, die das Endergebnis anpassen |

Die Regel wird über `pricing_rules()` des Plugins bekannt gemacht:

```python
    def pricing_rules(self):
        return (KayakInsuranceRule(),)
```

## Schritt 5: Aktivieren

**Variante eingebaut:** Datei nach `app/plugins/builtin/kayak.py` legen. Fertig,
der Loader findet sie beim nächsten Start.

**Variante extern:**

```powershell
# Windows
$env:RENTAL_PLUGIN_PATHS = "examples\plugins"
python run.py
```

```bash
# Linux / macOS
RENTAL_PLUGIN_PATHS=examples/plugins python run.py
```

## Schritt 6: Prüfen, ob es funktioniert

```bash
curl http://127.0.0.1:8000/api/meta
```

Im JSON muss der neue Typ unter `item_types` stehen, inklusive seiner
`attributes`. Im Dashboard erscheint er dann automatisch:

- Filterleiste unter „Gegenstände"
- Auswahl „Verleihtyp" beim Anlegen eines Gegenstands
- die typspezifischen Felder im Formular
- die Verleihart in der Bestandsverteilung

Preis prüfen ohne zu buchen:

```bash
curl -X POST http://127.0.0.1:8000/api/rentals/quote \
  -H "Content-Type: application/json" \
  -d '{"item_id": 10, "days": 3}'
```

## Schritt 7: Test schreiben

Der wichtigste Test ist nicht „funktioniert der neue Typ", sondern „funktioniert
der alte Typ weiterhin". Muster aus `tests/test_plugins.py`:

```python
def test_neuer_typ_veraendert_bestehende_ski_preise_nicht(registry):
    pricing_before = PricingService.with_defaults(registry.pricing_rules)
    ski = registry.build_item("ski", name="Ski", category="Standard",
                              daily_rate="25.00", attributes={"length_cm": 170})
    before = pricing_before.quote(ski, days=4).total

    registry.register(KayakPlugin())

    pricing_after = PricingService.with_defaults(registry.pricing_rules)
    after = pricing_after.quote(ski, days=4).total

    assert before == after == Decimal("90.00")
```

Wer ein externes Plugin testet, schreibt die Datei in `tmp_path` und ruft
`load_plugins([tmp_path])` auf.

## Checkliste

- [ ] `type_key` eindeutig und sprechend (`kayak`, nicht `typ3`)
- [ ] `display_name` für die Oberfläche gesetzt
- [ ] alle Pflichtfelder über `required=True` markiert
- [ ] Plugin-Klasse mit `key`, `name` und `PLUGIN = ...` exportiert
- [ ] eigene Preisregeln greifen nur auf den eigenen `type_key`
- [ ] `GET /api/meta` zeigt den neuen Typ
- [ ] Gegenstand anlegen und Verleih durchführen funktioniert im Dashboard
- [ ] Test vorhanden, der die bestehenden Typen absichert
- [ ] `pytest` grün

## Häufige Fehler

| Symptom | Ursache |
|---|---|
| Typ fehlt in `/api/meta` | Modul exportiert kein `PLUGIN`, oder Datei liegt nicht im erwarteten Verzeichnis |
| `PluginError: Verleihtyp 'x' ist bereits durch ein anderes Plugin belegt` | `type_key` doppelt vergeben |
| `ValidationError` beim Anlegen | Pflichtattribut fehlt oder Zahl ist keine Zahl |
| Preis unverändert | Regel liefert `applies()` False (falscher `type_key`) oder Regel-`key` überschreibt eine bestehende Regel |
| Felder fehlen im Formular | `attribute_fields()` nicht über `_fields` deklariert |
