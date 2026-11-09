# Architektur

## Überblick

Das System ist eine klassische Schichtenarchitektur mit einer Besonderheit: Die
Verleiharten sind nicht Teil des Kerns, sondern werden über eine Registry
eingespeist. Dadurch ist der Kern geschlossen gegenüber neuen Verleiharten
(Open-Closed-Prinzip) und trotzdem offen dafür.

```
┌──────────────────────────────────────────────────────────────┐
│  Browser-Dashboard (Jinja2 + Vanilla JS)   Swagger UI        │
└───────────────────────────┬──────────────────────────────────┘
                            │ HTTP/JSON, multipart
┌───────────────────────────▼──────────────────────────────────┐
│  app/api/          Routen, Transport-Schemata, Deps          │
│  app/main.py       App-Factory, Fehler-Handler, /            │
└───────────────────────────┬──────────────────────────────────┘
                            │ Service-Aufrufe (Dicts, Domänenobjekte)
┌───────────────────────────▼──────────────────────────────────┐
│  app/services/     ItemService, CustomerService,             │
│                    RentalService, DashboardService           │
└──────┬────────────────────┬───────────────────────┬──────────┘
       │                    │                       │
┌──────▼──────┐   ┌─────────▼────────┐   ┌──────────▼─────────┐
│ app/pricing │   │ app/repositories │   │ app/domain         │
│ Regeln,     │   │ SQLite-Zugriff   │   │ Entitäten, Geld,   │
│ Preisdienst │   │                  │   │ Fehler             │
└──────▲──────┘   └──────────────────┘   └────────────────────┘
       │ Preisregeln und Verleihtypen
┌──────┴───────────────────────────────────────────────────────┐
│  app/plugins/   Registry + Loader + builtin (ski, bike, ...)  │
└──────────────────────────────────────────────────────────────┘
```

`app/container.py` verdrahtet alle Implementierungen und wird von
`create_app()` genau einmal pro Prozess aufgebaut.

## Domänenmodell

```
          ┌──────────────────────────┐
          │ RentalItem  (ABC)        │
          │  name, category          │
          │  daily_rate: Decimal     │
          │  attributes: dict        │
          │  validate()              │
          │  attribute_fields()      │
          │  pricing_rules()         │
          └──────────▲───────────────┘
                     │ erbt
      ┌──────────────┼───────────────┬──────────────┐
   ┌──┴───┐      ┌───┴────┐     ┌────┴───┐    (weitere Plugins)
   │ Ski  │      │Snowboard│     │  Bike  │
   └──────┘      └────────┘     └────────┘

   Customer 1 ──── * Rental * ──── 1 RentalItem
      │
      └── IdDocument (Typ + Nummer + optionaler Scan)
```

Wichtige Entscheidungen:

- **`RentalItem` ist eine abstrakte Basisklasse, kein Datenbank-Record.** Die
  typspezifischen Felder liegen in `attributes` (JSON) und werden über
  `attribute_fields()` deklariert. Daraus baut die Oberfläche ihre Formulare und
  die Domäne validiert die Werte – ohne dass der Kern die Felder kennt.
- **`Rental` schreibt den Preis beim Anlegen fest** (`daily_rate`, `total`,
  `price_lines`). Eine Änderung der Preisregeln wirkt sich nicht rückwirkend auf
  bestehende Vorgänge aus.
- **Ein Verleihzeitraum ist halboffen** `[start_date, start_date + days)`. Ein
  Anschlussverleih am Rückgabetag ist daher ohne Konflikt möglich.

## Preispipeline

```
RentalItem ─┐
Verleihdauer├─▶ PriceRequest ──▶ [Regel 10] ─▶ [Regel 30] ─▶ [Regel 40] ─▶ PriceQuote
Startdatum  │                     Duration     Plugin        Kategorie      (Positionen
Kunde      ─┘                     setzt base   addiert       rechnet auf    + Summe)
                                                             base
```

- `PricingService` hält die Regeln sortiert nach `priority` und führt sie aus.
- Jede Regel entscheidet über `applies(request)`, ob sie gilt, und liefert über
  `apply(request, state)` null oder mehr `PriceLine`.
- `DurationRateRule` (Priorität 10) setzt `state.base`. Alle späteren Regeln
  rechnen auf diesen Zwischenstand – dadurch ist die Reihenfolge fachlich
  bedeutsam und nicht zufällig.
- Objektabhängige Regeln (`item.pricing_rules()`) überschreiben Regeln mit
  gleichem `key`. So kann ein einzelner Gegenstand eine Sonderregel bekommen,
  ohne die globale Konfiguration zu ändern.
- Neue Regeln kommen über Plugins. `PluginRegistry` benachrichtigt den
  Preisdienst über einen Listener, damit auch zur Laufzeit registrierte Plugins
  sofort wirken.

## Plugin-Lebenszyklus

1. `load_plugins()` importiert alle Module aus `app/plugins/builtin/`, die ein
   Objekt `PLUGIN` exportieren.
2. Zusätzlich werden Verzeichnisse aus `RENTAL_PLUGIN_PATHS` durchsucht und
   `.py`-Dateien per `importlib` geladen.
3. Jedes Plugin wird bei `PluginRegistry.register()` geprüft: doppelte
   Plugin-Keys, doppelte `type_key`s und doppelte Regel-Keys führen zu einem
   `PluginError`, bevor irgendetwas übernommen wird (kein halb registriertes
   Plugin).
4. Die Registry stellt danach `item_types`, `pricing_rules`,
   `id_document_types` und `describe()` für die API bereit.

Das Frontend kennt keine Verleiharten. Es liest `GET /api/meta` und rendert
Eingabefelder anhand der dort gemeldeten `attributes`.

## Persistenz

Drei Tabellen, keine Migrationen (Schema ist idempotent, `schema.sql`):

```sql
customers (id, first_name, last_name, email, phone,
           id_type, id_number, id_file, created_at)

items     (id, name, type_key, category, daily_rate_cents,
           attributes, active, created_at)

rentals   (id, item_id, customer_id, start_date, days, due_date,
           daily_rate_cents, total_cents, price_lines, created_at, returned_at)
```

- Beträge als ganzzahlige Cent, Attribute und Rechnungspositionen als JSON.
- `due_date` ist redundant zu `start_date + days`, macht aber
  Bereichsabfragen („heute fällig", „überfällig") ohne Rechnen in SQL möglich.
- `foreign_keys = ON`. Ein Gegenstand mit Verleihhistorie wird nicht gelöscht,
  sondern deaktiviert (`ItemService.delete_item`).

## Fehlerbehandlung

| Klasse | HTTP | Beispiel |
|---|---|---|
| `ValidationError` | 422 | Verleihdauer 0, unbekannter Verleih- oder Ausweistyp |
| `NotFoundError` | 404 | Gegenstand, Kunde oder Vorgang existiert nicht |
| `ConflictError` | 409 | Kunde ohne Ausweis, doppelte Rückgabe, Kunde mit Historie löschen |
| `ItemUnavailableError` | 409 | Gegenstand im Zeitraum bereits verliehen oder deaktiviert |
| `PluginError` | 500 | Doppelter Plugin-Key, defektes externes Plugin |

Die API-Schicht registriert einen einzigen Handler (`app/main.py`) und liefert
`{"error": <code>, "message": <text>}`. Services kennen kein HTTP.

## Entwurfsentscheidungen (kurz begründet)

1. **FastAPI statt Flask/Django.** Automatische OpenAPI-Dokumentation,
   Typprüfung der Eingaben über Pydantic, geringer Boilerplate.
2. **SQLite über die Standardbibliothek.** Keine Serverinstallation, ein File,
   für einen Verleihschalter ausreichend. Ein Wechsel auf PostgreSQL beträfe nur
   `app/repositories/`.
3. **Attribute als JSON statt Vererbungshierarchie in der Datenbank.** Neue
   Verleiharten brauchen keine Schemaänderung. Preis der Entscheidung: SQL kann
   typspezifische Felder nicht filtern – für dieses System nicht nötig.
4. **Eine Regelkette statt einer Formel.** Rabatte, Zuschläge und
   Plugin-Aufschläge sind unabhängig testbar und in der Reihenfolge
   dokumentiert. Eine monolithische `calculate_price()`-Funktion wäre kürzer,
   aber nicht erweiterbar.
5. **Vanilla JS statt Framework.** Kein Build-Schritt, kein `node_modules`, die
   Oberfläche bleibt für Dritte lesbar. Die API ist so geschnitten, dass ein
   späterer Wechsel auf ein Framework ohne Backend-Änderung möglich ist.
6. **Listener in der Registry.** Damit funktioniert sowohl das Laden beim Start
   als auch eine Registrierung zur Laufzeit (Tests nutzen das ausführlich).
