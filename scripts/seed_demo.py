"""Legt realistische Beispieldaten an.

    python scripts/seed_demo.py

Bricht ab, wenn die Datenbank bereits Gegenstände enthält.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Settings  # noqa: E402
from app.container import build_container  # noqa: E402

TODAY = date.today()


def main() -> None:
    container = build_container(Settings.from_env())

    if container.items.list_items(include_inactive=True):
        print("Datenbank enthält bereits Gegenstände – Seed wird übersprungen.")
        return

    items = {}
    for key, data in {
        "redster": dict(
            type_key="ski", name="Atomic Redster S9", category="Premium", daily_rate="39.00",
            attributes={"length_cm": 170, "skill_level": "Profi", "service_package": True},
        ),
        "deacon": dict(
            type_key="ski", name="Völkl Deacon 76", category="Standard", daily_rate="29.00",
            attributes={"length_cm": 175, "skill_level": "Fortgeschritten"},
        ),
        "experience": dict(
            type_key="ski", name="Rossignol Experience 80", category="Standard", daily_rate="27.00",
            attributes={"length_cm": 168, "skill_level": "Fortgeschritten"},
        ),
        "supershape": dict(
            type_key="ski", name="Head Supershape e-Speed", category="Premium", daily_rate="35.00",
            attributes={"length_cm": 163, "skill_level": "Profi"},
        ),
        "kinder": dict(
            type_key="ski", name="Blizzard Kinder-Ski", category="Kinder", daily_rate="18.00",
            attributes={"length_cm": 130, "skill_level": "Anfänger"},
        ),
        "burton": dict(
            type_key="snowboard", name="Burton Custom", category="Standard", daily_rate="32.00",
            attributes={"length_cm": 156, "stance": "Regular", "boots_included": True},
        ),
        "raygun": dict(
            type_key="snowboard", name="K2 Raygun Pop", category="Standard", daily_rate="30.00",
            attributes={"length_cm": 158, "stance": "Goofy"},
        ),
        "citybike": dict(
            type_key="bike", name="Trek FX 2 Citybike", category="Standard", daily_rate="22.00",
            attributes={"bike_kind": "City", "frame_size": "M", "helmet_included": True},
        ),
        "ebike": dict(
            type_key="bike", name="Cube Kathmandu E-Bike", category="Premium", daily_rate="45.00",
            attributes={"bike_kind": "E-Bike", "frame_size": "L"},
        ),
    }.items():
        items[key] = container.items.create_item(data)

    customers = {
        "anna": container.customers.create_customer(
            {"first_name": "Anna", "last_name": "Müller", "email": "anna.mueller@example.at",
             "phone": "+43 660 1234567", "id_type": "id_card", "id_number": "AT-4471902"}
        ),
        "stefan": container.customers.create_customer(
            {"first_name": "Stefan", "last_name": "Berger", "email": "s.berger@example.at",
             "id_type": "passport", "id_number": "P-9982114"}
        ),
        "lena": container.customers.create_customer(
            {"first_name": "Lena", "last_name": "Hofer", "phone": "+43 676 9988776",
             "id_type": "drivers_license", "id_number": "F-7712345"}
        ),
        "tobias": container.customers.create_customer(
            {"first_name": "Tobias", "last_name": "Wagner", "email": "t.wagner@example.at",
             "id_type": "id_card", "id_number": "AT-5580741"}
        ),
    }

    def rent(item_key: str, customer_key: str, start: date, days: int) -> int:
        rental = container.rentals.create_rental(
            {
                "item_id": items[item_key].id,
                "customer_id": customers[customer_key].id,
                "start_date": start.isoformat(),
                "days": days,
            }
        )
        return rental.id

    # Aktive Verleihe
    rent("redster", "anna", TODAY - timedelta(days=2), 5)
    rent("burton", "stefan", TODAY - timedelta(days=1), 3)
    rent("ebike", "lena", TODAY, 4)

    # Überfällig
    rent("citybike", "tobias", TODAY - timedelta(days=9), 2)

    # Bereits zurückgegeben
    returned_id = rent("deacon", "tobias", TODAY - timedelta(days=14), 3)
    container.rentals.return_rental(returned_id)
    returned_id = rent("experience", "anna", TODAY - timedelta(days=8), 2)
    container.rentals.return_rental(returned_id)
    returned_id = rent("raygun", "stefan", TODAY - timedelta(days=20), 4)
    container.rentals.return_rental(returned_id)

    # Bevorstehende Rückgabe morgen
    rent("supershape", "lena", TODAY - timedelta(days=1), 2)

    print(f"Seed abgeschlossen: {len(items)} Gegenstände, {len(customers)} Kunden.")


if __name__ == "__main__":
    main()
