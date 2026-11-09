# CLAUDE.md – Projekt- und Entwicklungsrichtlinien

Diese Datei beschreibt, wie in diesem Repository gearbeitet wird. Sie ist die
verbindliche Kurzreferenz für Menschen und für KI-Assistenten.

## Was ist das Projekt

Ein Verleihsystem für Sportausrüstung. Primär Ski-Verleih, architektonisch aber
ein allgemeines Verleihsystem: Verleiharten (Ski, Snowboard, Bike, ...) sind
Plugins, keine Sonderfälle im Kern.

- Backend: Python 3.11+, FastAPI, SQLite (Standardbibliothek `sqlite3`)
- Frontend: Jinja2-Template plus Vanilla JavaScript, kein Build-Schritt
- Tests: pytest
- Sprache im Code: Bezeichner englisch, Fachbegriffe und Texte deutsch

## Befehle

```bash
# Umgebung
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

# Starten
python run.py                      # http://127.0.0.1:8000
# alternativ: uvicorn app.server:app --reload

# Beispieldaten
python scripts/seed_demo.py

# Tests
pytest                             # gesamte Suite
pytest tests/test_pricing.py -q    # einzelne Datei
```

Die Datenbank liegt unter `data/rental.db` und ist nicht versioniert. Für einen
frischen Stand `data/` löschen und den Seed erneut ausführen.

## Architekturregeln

Die Abhängigkeiten zeigen nach innen. Das ist keine Empfehlung, sondern die
Grundlage der Erweiterbarkeit:

```
api ──▶ services ──▶ domain
          │
          ├──▶ repositories (SQLite)
          └──▶ pricing ◀── plugins
```

- `app/domain/` kennt weder FastAPI noch SQL noch Dateien. Keine Importe aus
  `api`, `repositories` oder `services` in dieser Schicht.
- `app/api/` enthält keine Fachlogik: Request lesen, Service aufrufen,
  Ergebnis serialisieren. Keine Preise berechnen, keine Validierung von
  Geschäftsregeln.
- `app/services/` orchestriert. Preise entstehen ausschließlich im
  `PricingService`, nie in einem Service oder einer Route.
- `app/repositories/` bildet Domänenobjekte auf SQL ab. Keine Fachlogik.
- `app/container.py` ist der einzige Ort, an dem konkrete Klassen instanziiert
  und verdrahtet werden.
- Der Kern kennt keine konkreten Verleiharten. Wer `if type_key == "ski"`
  schreiben will, gehört in ein Plugin.

## Geld und Daten

- Beträge sind `Decimal` mit zwei Nachkommastellen, intern als ganzzahlige Cent
  gespeichert (`app/domain/money.py`). Niemals `float` für Geld verwenden.
- Rundung immer über `money()`, `percent_of()` oder `to_cents()`.
- Datumswerte: `date` in der Domäne, ISO-Strings (`JJJJ-MM-TT`) in DB und API.
- Zeitzonen spielen keine Rolle; alles ist lokale Zeit.

## Wie erweitere ich was

| Ziel | Ort | Vorgehen |
|---|---|---|
| Neuer Verleihtyp | `app/plugins/builtin/` oder externes Plugin | `RentalItem`-Unterklasse + `RentalPlugin`, siehe `docs/adding-rental-types.md` |
| Neue Preisregel | Plugin (bevorzugt) oder `app/pricing/rules.py` (Kernregel) | von `PricingRule` erben, `key`, `priority`, `apply()` implementieren |
| Neuer Ausweistyp | Plugin | `id_document_types()` ergänzen, z. B. in `identity.py` |
| Neue API-Route | `app/api/routes_*.py` + Service | Route bleibt dünn, Logik in den Service |
| Neue Kennzahl | `app/services/dashboard.py` | im `stats()`-Dict ergänzen und im Frontend rendern |
| Neue Tabelle/Spalte | `app/repositories/schema.sql` | Schema ist idempotent, keine Migrationen im Projekt |

## Konventionen im Code

- Typannotationen überall dort, wo sie die Lesbarkeit erhöhen; `from __future__
  import annotations` ist gesetzt.
- Fachliche Fehler: `app/domain/errors.py` (`ValidationError`, `NotFoundError`,
  `ConflictError`, `ItemUnavailableError`). Sie tragen ihren HTTP-Status, die
  API-Schicht fängt sie zentral in `app/main.py`.
- Keine `print`-Ausgaben im Anwendungscode. Ausnahmen: `scripts/`.
- Docstrings auf Deutsch, kurz, im Imperativ oder als Aussagesatz.
- Kommentare erklären das Warum, nicht das Was.
- Namensgebung: `snake_case` in Python, `camelCase` im JavaScript,
  `kebab-case` für CSS-Klassen.

## Tests

- Jede neue Fachregel bekommt mindestens einen Test.
- Neue Verleihtypen: Test, der beweist, dass bestehende Typen unverändert
  funktionieren (`tests/test_plugins.py` ist das Muster).
- Tests dürfen nicht vom heutigen Datum abhängen, wenn sie Status prüfen –
  relative Bezugspunkte wie `FUTURE = date.today() + timedelta(days=30)`
  verwenden.
- Vor jedem Commit: `pytest` muss grün sein.
- Fixtures liegen in `tests/conftest.py` (`make_item`, `make_customer`,
  `make_rental`, `container`, `client`).

## Was man nicht tun soll

- Preise in Services, Routen oder im Frontend berechnen.
- Verleiharten im Kern mit `if`/`elif` unterscheiden.
- Die Abhängigkeitsrichtung umdrehen (z. B. Domäne importiert FastAPI).
- Geld mit `float` rechnen.
- Bestehende Tabellenstrukturen stillschweigend ändern, ohne `data/` neu
  aufzubauen.
- Das ZIP der Abgabe oder die Datenbank committen (`data/` ist ignoriert).

## Stand

Die Anwendung ist funktionsfähig: Verleih, Rückgabe, Kunden mit Ausweisen,
Preisregeln, Dashboard mit Kennzahlen, Plugin-System mit drei eingebauten
Verleiharten. Offene Punkte sind in der README unter „Bewusste Entscheidungen
und Grenzen" dokumentiert.
