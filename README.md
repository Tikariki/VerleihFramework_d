# Verleih-Framework – allgemeines Verleihsystem mit Plugin-Architektur

Abgabe zu **Aufgabe d) – Zusatzaufgabe**. Ein erweiterbares Framework, in dem
unterschiedliche Verleihgegenstände über eine gemeinsame Abstraktion verwaltet
werden. Ski, Snowboards und Fahrräder sind bereits integriert; weitere
Verleiharten kommen als Plugin dazu – ohne Änderung am Kern.

Dieses Projekt ist unabhängig von den Abgaben zu a), b) und c) lauffähig. Es
demonstriert die Architektur, die hinter dem Ski-Verleih (a/b) steckt, und zeigt
sie an drei Verleiharten plus einem externen Beispiel-Plugin (Kajak).

Das System besteht aus einer FastAPI-Anwendung mit SQLite-Persistenz, einer
zentralen Preisberechnung und einem Dashboard im Browser. Es gibt kein
Build-Werkzeug und keinen Node-Zwang: klonen, Abhängigkeiten installieren,
starten.

## Funktionen

**Verleihbetrieb**

- Verleihgegenstände anlegen, bearbeiten, löschen (mit Historie: Löschen wird zu
  Deaktivieren, damit alte Vorgänge nachvollziehbar bleiben)
- Verfügbarkeit pro Zeitraum prüfen, Doppelverleihungen werden abgelehnt
- Verleihvorgänge mit Beginn und Dauer anlegen, Preis wird beim Anlegen
  festgeschrieben
- Rückgabe verbuchen, überfällige Vorgänge werden automatisch erkannt
- Verleihhistorie pro Gegenstand und pro Kunde

**Kunden**

- Kunden mit Vorname, Nachname, Kontaktdaten
- Ausweis mit Typ und Nummer, optional als Scan/Foto (JPG, PNG, PDF bis 5 MB)
- ohne hinterlegten Ausweis lehnt das System den Verleih ab
- Ausweistypen sind erweiterbar (Plugin, nicht Enum im Kern)

**Dashboard**

- Kennzahlen: verliehen, verfügbar, aktive Vorgänge, Einnahmen (Tag/Monat/gesamt)
- anstehende Rückgaben der nächsten sieben Tage, überfällige Vorgänge markiert
- Bestandsverteilung nach Verleihart
- Verwaltung von Gegenständen, Kunden und Vorgängen direkt in der Oberfläche
- Live-Preisvorschau beim Anlegen eines Verleihs
- Übersicht der aktiven Preisregeln

**Architektur**

- `RentalItem` als gemeinsame Abstraktion, konkrete Typen als Plugins
- zentrale, modulare Preisberechnung über eine Regelkette
- Trennung von Domäne, Anwendungsservices, Persistenz und HTTP-Schicht
- 81 automatisierte Tests (pytest)

## Schnellstart

Voraussetzung: Python 3.11 oder neuer.

**Windows (PowerShell oder VS-Code-Terminal)**

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python scripts/seed_demo.py
python run.py
```

**Linux / macOS**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/seed_demo.py
python run.py
```

Danach im Browser:

- Dashboard: <http://127.0.0.1:8000>
- API-Dokumentation (Swagger UI): <http://127.0.0.1:8000/docs>

`scripts/seed_demo.py` legt neun Gegenstände, vier Kunden und acht
Verleihvorgänge an, damit das Dashboard nicht leer startet. Der Seed bricht ab,
wenn die Datenbank bereits Gegenstände enthält.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Die Testsuite deckt Preisberechnung, Verleih- und Rückgabeprozesse,
Verfügbarkeit, Kundenverwaltung, die HTTP-Schnittstelle und die
Erweiterbarkeit durch neue Verleihtypen ab.

## Projektstruktur

```
Linz_Aufgabe_1/
├── app/
│   ├── main.py            FastAPI-App-Factory, Fehlerbehandlung, Dashboard-Route
│   ├── server.py          ASGI-Einstiegspunkt (uvicorn app.server:app)
│   ├── container.py       Composition Root: verdrahtet alle Implementierungen
│   ├── config.py          Pfade und Einstellungen (über Umgebungsvariablen)
│   ├── domain/            Entitäten, Wertobjekte, fachliche Fehler, Geldrechnung
│   ├── pricing/           Preisregeln und Preisdienst
│   ├── plugins/           Plugin-Schnittstelle, Registry, Loader
│   │   ├── api.py         RentalPlugin, IdDocumentType, PluginRegistry
│   │   ├── loader.py      lädt eingebaute und externe Plugins
│   │   └── builtin/       ski, snowboard, bike, identity
│   ├── services/          Geschäftslogik: items, customers, rentals, dashboard
│   ├── repositories/      SQLite-Zugriff, Schema
│   ├── api/               HTTP-Routen und Transport-Schemata
│   ├── templates/         Dashboard (Jinja2)
│   └── static/            CSS und JavaScript des Dashboards
├── tests/                 pytest-Suite
├── scripts/seed_demo.py   Beispieldaten
├── docs/                  Architektur, Plugin-System, Anleitung neue Typen
├── run.py                 Startskript
├── requirements.txt       Laufzeitabhängigkeiten
└── CLAUDE.md              Projekt- und Entwicklungsrichtlinien
```

## Architektur in Kürze

Die Abhängigkeiten zeigen ausschließlich nach innen:

```
api (HTTP) ──▶ services ──▶ domain
                   │
                   ├──▶ repositories ──▶ SQLite
                   └──▶ pricing ◀── plugins
```

- **domain** enthält keine Infrastruktur und kein HTTP. `RentalItem`,
  `Customer`, `Rental` und die Geldrechnung sind reine Fachlogik.
- **pricing** kennt nur `PriceRequest`/`PriceState`. Regeln werden nach
  Priorität ausgeführt, jede Regel liefert Rechnungspositionen.
- **plugins** liefern Verleihtypen, Preisregeln und Ausweistypen. Der Kern
  kennt keinen der konkreten Typen.
- **services** orchestrieren: Verfügbarkeit, Preis, Persistenz, Regeln.
- **api** ist eine dünne Fassade und übersetzt fachliche Fehler in HTTP-Codes.
- **container.py** ist der einzige Ort, an dem konkrete Klassen instanziiert
  werden.

Details: [docs/architecture.md](docs/architecture.md)

## Preismodell

Die Preisberechnung ist eine Kette unabhängiger Regeln. Jede Regel liest den
bisherigen Zwischenstand (`PriceState.base`) und liefert ihre Positionen.

| Priorität | Regel | Wirkung |
|---|---|---|
| 10 | `duration` | Tagespreis × Dauer, ab 4 Tagen −10 %, ab 7 Tagen −20 % |
| 30 | `ski_service_fee` | Service-Paket Ski: +14,90 € pauschal |
| 30 | `bike_ebike_surcharge` | E-Bike: +20 % auf den Grundpreis |
| 35 | (Plugin-eigene Regeln) | frei definierbar |
| 40 | `category` | Premium +15 %, Kinder −10 % auf den Zwischenstand |

Staffel und Kategorie-Zuordnung sind Konstruktorparameter
(`DurationRateRule(tiers=...)`, `CategorySurchargeRule(mapping=...)`) und damit
ohne Architekturänderung anpassbar. Plugins bringen eigene Regeln mit; sie
werden über den `PluginRegistry` automatisch in den Preisdienst übernommen.

Beispiel: 7 Tage Kinder-Ski zu 18,00 €
`126,00 − 20 % = 100,80 − 10 % = 90,72 €`

## Plugin-System in Kürze

Ein Plugin ist eine Klasse, die von `RentalPlugin` erbt und `RentalItem`-
Unterklassen, Preisregeln und/oder Ausweistypen beisteuert. Eingebaute Plugins
liegen unter `app/plugins/builtin/`, externe als `.py`-Datei in einem
Verzeichnis, das über `RENTAL_PLUGIN_PATHS` gesetzt wird.

```python
class Kayak(RentalItem):
    type_key = "kayak"
    display_name = "Kajak"
    _fields = (AttributeField("seats", "Sitzplätze", "number", required=True),)
```

Das Dashboard liest die verfügbaren Typen über `GET /api/meta` und baut die
Formulare automatisch – ein neuer Typ erscheint ohne Frontend-Änderung.

Anleitung: [docs/adding-rental-types.md](docs/adding-rental-types.md)

## API-Überblick

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/api/meta` | Verleihtypen, Ausweistypen, Preisregeln, Plugins |
| GET | `/api/dashboard` | Kennzahlen für das Dashboard |
| GET | `/api/items` | Gegenstände (`include_inactive`, `type_key`) |
| GET | `/api/items/available` | freie Gegenstände (`start`, `days`) |
| POST | `/api/items` | Gegenstand anlegen |
| PUT | `/api/items/{id}` | Gegenstand bearbeiten |
| DELETE | `/api/items/{id}` | löschen bzw. deaktivieren |
| GET | `/api/customers` | Kunden |
| POST | `/api/customers` | Kunde anlegen |
| POST | `/api/customers/{id}/document` | Ausweis hinterlegen (multipart) |
| GET | `/api/rentals` | Vorgänge (`status`, `item_id`, `customer_id`, `limit`) |
| POST | `/api/rentals` | Verleih anlegen |
| POST | `/api/rentals/quote` | Preis berechnen ohne Buchung |
| POST | `/api/rentals/{id}/return` | Rückgabe verbuchen |

Fachliche Fehler kommen als JSON: `{"error": "item_unavailable", "message": "..."}`
mit passendem Status (404, 409, 422).

## Konfiguration

| Variable | Standard | Bedeutung |
|---|---|---|
| `RENTAL_DATA_DIR` | `./data` | Ablage für Datenbank und Uploads |
| `RENTAL_DB_PATH` | `<data>/rental.db` | Pfad der SQLite-Datei |
| `RENTAL_UPLOAD_DIR` | `<data>/uploads` | Ziel für Ausweis-Scans |
| `RENTAL_PLUGIN_PATHS` | leer | Verzeichnisse mit externen Plugins (getrennt durch `;` bzw. `:`) |
| `RENTAL_CURRENCY` | `EUR` | Währungskennzeichen für die Anzeige |

## Bewusste Entscheidungen und Grenzen

- **SQLite statt Server-Datenbank**: keine Installation nötig, ausreichend für
  einen Verleihbetrieb, Wechsel wäre auf `repositories/` begrenzt.
- **Server-gerendertes Dashboard mit Vanilla JS**: kein Build-Schritt, direkt
  lesbar, keine Toolchain-Abhängigkeit. Für ein stark wachsendes Frontend wäre
  ein Framework sinnvoll.
- **Kein Login**: Das System ist ein internes Werkzeug für die Verleihstation,
  Benutzerverwaltung war nicht Teil der Aufgabe.
- **Preis wird beim Verleih festgeschrieben**: spätere Preisänderungen gelten
  nur für neue Vorgänge. Das ist bewusst so, damit Rechnungen stabil bleiben.
- **Kein Zahlungsverkehr**: Einnahmen werden aus den Verleihbeträgen berechnet,
  Zahlungen werden nicht erfasst.
