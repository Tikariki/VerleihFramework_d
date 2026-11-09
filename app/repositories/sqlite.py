"""Konkrete SQLite-Repositories.

Die Repositories kennen nur Domänenobjekte, keine HTTP- oder UI-Belange.
Damit bleibt die Geschäftslogik unabhängig von der Persistenztechnik: ein
Wechsel auf PostgreSQL beträfe ausschließlich dieses Modul.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from typing import Any

from ..domain.errors import NotFoundError, ValidationError
from ..domain.models import Customer, IdDocument, Rental, RentalItem
from ..domain.money import from_cents, to_cents
from ..plugins.api import PluginRegistry
from .database import Database

BASE_SELECT = """
    SELECT r.*,
           i.name AS item_name,
           i.type_key AS item_type,
           c.first_name || ' ' || c.last_name AS customer_name
      FROM rentals r
      JOIN items i     ON i.id = r.item_id
      JOIN customers c ON c.id = r.customer_id
"""


class ItemRepository:
    def __init__(self, database: Database, registry: PluginRegistry) -> None:
        self._db = database
        self._registry = registry

    # ------------------------------------------------------------------
    def _to_item(self, row: sqlite3.Row) -> RentalItem:
        try:
            return self._registry.build_item(
                row["type_key"],
                id=row["id"],
                name=row["name"],
                category=row["category"],
                daily_rate=from_cents(row["daily_rate_cents"]),
                attributes=json.loads(row["attributes"] or "{}"),
                active=bool(row["active"]),
                created_at=datetime.fromisoformat(row["created_at"]),
            )
        except ValidationError as exc:
            raise ValidationError(
                f"Gegenstand #{row['id']} kann nicht geladen werden: {exc.message}"
            ) from exc

    def list(self, include_inactive: bool = False) -> list[RentalItem]:
        query = "SELECT * FROM items"
        if not include_inactive:
            query += " WHERE active = 1"
        query += " ORDER BY type_key, name COLLATE NOCASE"
        with self._db.session() as connection:
            return [self._to_item(row) for row in connection.execute(query)]

    def find(self, item_id: int) -> RentalItem | None:
        with self._db.session() as connection:
            row = connection.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        return self._to_item(row) if row else None

    def get(self, item_id: int) -> RentalItem:
        item = self.find(item_id)
        if item is None:
            raise NotFoundError(f"Verleihgegenstand #{item_id} wurde nicht gefunden.")
        return item

    def add(self, item: RentalItem) -> RentalItem:
        with self._db.session() as connection:
            cursor = connection.execute(
                """INSERT INTO items (name, type_key, category, daily_rate_cents,
                                      attributes, active, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    item.name,
                    item.type_key,
                    item.category,
                    to_cents(item.daily_rate),
                    json.dumps(item.attributes, ensure_ascii=False),
                    int(item.active),
                    item.created_at.isoformat(timespec="seconds"),
                ),
            )
            item.id = int(cursor.lastrowid)
        return item

    def update(self, item: RentalItem) -> RentalItem:
        if item.id is None:
            raise ValidationError("Der Gegenstand hat keine ID.")
        with self._db.session() as connection:
            connection.execute(
                """UPDATE items
                      SET name = ?, type_key = ?, category = ?, daily_rate_cents = ?,
                          attributes = ?, active = ?
                    WHERE id = ?""",
                (
                    item.name,
                    item.type_key,
                    item.category,
                    to_cents(item.daily_rate),
                    json.dumps(item.attributes, ensure_ascii=False),
                    int(item.active),
                    item.id,
                ),
            )
        return item

    def delete(self, item_id: int) -> None:
        """Löscht hart; schlägt fehl, wenn Verleihvorgänge existieren."""
        with self._db.session() as connection:
            connection.execute("DELETE FROM items WHERE id = ?", (item_id,))

    def rental_count(self, item_id: int) -> int:
        with self._db.session() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS n FROM rentals WHERE item_id = ?", (item_id,)
            ).fetchone()
        return int(row["n"])


class CustomerRepository:
    def __init__(self, database: Database) -> None:
        self._db = database

    def _to_customer(self, row: sqlite3.Row) -> Customer:
        document = None
        if row["id_number"]:
            document = IdDocument(
                type_key=row["id_type"] or "id_card",
                number=row["id_number"],
                file_name=row["id_file"],
            )
        return Customer(
            id=row["id"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            email=row["email"] or "",
            phone=row["phone"] or "",
            id_document=document,
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def list(self) -> list[Customer]:
        with self._db.session() as connection:
            rows = connection.execute(
                "SELECT * FROM customers ORDER BY last_name COLLATE NOCASE, first_name"
            ).fetchall()
        return [self._to_customer(row) for row in rows]

    def find(self, customer_id: int) -> Customer | None:
        with self._db.session() as connection:
            row = connection.execute(
                "SELECT * FROM customers WHERE id = ?", (customer_id,)
            ).fetchone()
        return self._to_customer(row) if row else None

    def get(self, customer_id: int) -> Customer:
        customer = self.find(customer_id)
        if customer is None:
            raise NotFoundError(f"Kunde #{customer_id} wurde nicht gefunden.")
        return customer

    def add(self, customer: Customer) -> Customer:
        document = customer.id_document
        with self._db.session() as connection:
            cursor = connection.execute(
                """INSERT INTO customers (first_name, last_name, email, phone,
                                          id_type, id_number, id_file, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    customer.first_name,
                    customer.last_name,
                    customer.email,
                    customer.phone,
                    document.type_key if document else None,
                    document.number if document else None,
                    document.file_name if document else None,
                    customer.created_at.isoformat(timespec="seconds"),
                ),
            )
            customer.id = int(cursor.lastrowid)
        return customer

    def update(self, customer: Customer) -> Customer:
        if customer.id is None:
            raise ValidationError("Der Kunde hat keine ID.")
        document = customer.id_document
        with self._db.session() as connection:
            connection.execute(
                """UPDATE customers
                      SET first_name = ?, last_name = ?, email = ?, phone = ?,
                          id_type = ?, id_number = ?, id_file = ?
                    WHERE id = ?""",
                (
                    customer.first_name,
                    customer.last_name,
                    customer.email,
                    customer.phone,
                    document.type_key if document else None,
                    document.number if document else None,
                    document.file_name if document else None,
                    customer.id,
                ),
            )
        return customer

    def delete(self, customer_id: int) -> None:
        with self._db.session() as connection:
            connection.execute("DELETE FROM customers WHERE id = ?", (customer_id,))

    def rental_count(self, customer_id: int) -> int:
        with self._db.session() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS n FROM rentals WHERE customer_id = ?", (customer_id,)
            ).fetchone()
        return int(row["n"])


class RentalRepository:
    def __init__(self, database: Database) -> None:
        self._db = database

    # ------------------------------------------------------------------
    def _to_rental(self, row: sqlite3.Row) -> Rental:
        return Rental(
            id=row["id"],
            item_id=row["item_id"],
            customer_id=row["customer_id"],
            start_date=date.fromisoformat(row["start_date"]),
            days=row["days"],
            daily_rate=from_cents(row["daily_rate_cents"]),
            total=from_cents(row["total_cents"]),
            price_lines=json.loads(row["price_lines"] or "[]"),
            created_at=datetime.fromisoformat(row["created_at"]),
            returned_at=datetime.fromisoformat(row["returned_at"]) if row["returned_at"] else None,
            item_name=row["item_name"],
            item_type=row["item_type"],
            customer_name=row["customer_name"],
        )

    def add(self, rental: Rental) -> Rental:
        with self._db.session() as connection:
            cursor = connection.execute(
                """INSERT INTO rentals (item_id, customer_id, start_date, days, due_date,
                                        daily_rate_cents, total_cents, price_lines, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    rental.item_id,
                    rental.customer_id,
                    rental.start_date.isoformat(),
                    rental.days,
                    rental.due_date.isoformat(),
                    to_cents(rental.daily_rate),
                    to_cents(rental.total),
                    json.dumps(rental.price_lines, ensure_ascii=False),
                    rental.created_at.isoformat(timespec="seconds"),
                ),
            )
            rental.id = int(cursor.lastrowid)
        return rental

    def find(self, rental_id: int) -> Rental | None:
        with self._db.session() as connection:
            row = connection.execute(
                BASE_SELECT + " WHERE r.id = ?", (rental_id,)
            ).fetchone()
        return self._to_rental(row) if row else None

    def get(self, rental_id: int) -> Rental:
        rental = self.find(rental_id)
        if rental is None:
            raise NotFoundError(f"Verleihvorgang #{rental_id} wurde nicht gefunden.")
        return rental

    def mark_returned(self, rental_id: int, when: datetime) -> None:
        with self._db.session() as connection:
            connection.execute(
                "UPDATE rentals SET returned_at = ? WHERE id = ?",
                (when.isoformat(timespec="seconds"), rental_id),
            )

    # ------------------------------------------------------------------
    def list(
        self,
        status: str | None = None,
        item_id: int | None = None,
        customer_id: int | None = None,
        limit: int | None = None,
        today: date | None = None,
    ) -> list[Rental]:
        today = today or date.today()
        conditions: list[str] = []
        params: list[Any] = []

        if status == "active":
            conditions.append("r.returned_at IS NULL")
        elif status == "returned":
            conditions.append("r.returned_at IS NOT NULL")
        elif status == "overdue":
            conditions.append("r.returned_at IS NULL AND r.due_date < ?")
            params.append(today.isoformat())
        elif status not in (None, "", "all"):
            raise ValidationError(f"Unbekannter Status '{status}'.")

        if item_id is not None:
            conditions.append("r.item_id = ?")
            params.append(item_id)
        if customer_id is not None:
            conditions.append("r.customer_id = ?")
            params.append(customer_id)

        query = BASE_SELECT
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY r.start_date DESC, r.id DESC"
        if limit:
            query += f" LIMIT {int(limit)}"

        with self._db.session() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._to_rental(row) for row in rows]

    def open_rentals(self) -> list[Rental]:
        return self.list(status="active")

    def active_for_item(self, item_id: int, today: date | None = None) -> list[Rental]:
        return self.list(status="active", item_id=item_id, today=today)

    def overlapping(
        self,
        item_id: int,
        start: date,
        end: date,
    ) -> list[Rental]:
        """Offene Verleihvorgänge, die sich mit [start, end) überschneiden."""
        with self._db.session() as connection:
            rows = connection.execute(
                BASE_SELECT
                + """ WHERE r.item_id = ?
                        AND r.returned_at IS NULL
                        AND r.start_date < ?
                        AND r.due_date > ?
                   ORDER BY r.start_date""",
                (item_id, end.isoformat(), start.isoformat()),
            ).fetchall()
        return [self._to_rental(row) for row in rows]

    def due_between(self, start: date, end: date) -> list[Rental]:
        with self._db.session() as connection:
            rows = connection.execute(
                BASE_SELECT
                + """ WHERE r.returned_at IS NULL
                        AND r.due_date >= ?
                        AND r.due_date <= ?
                   ORDER BY r.due_date""",
                (start.isoformat(), end.isoformat()),
            ).fetchall()
        return [self._to_rental(row) for row in rows]

    def revenue_between(self, start: date, end: date) -> Any:
        with self._db.session() as connection:
            row = connection.execute(
                """SELECT COALESCE(SUM(total_cents), 0) AS cents
                     FROM rentals
                    WHERE start_date >= ? AND start_date <= ?""",
                (start.isoformat(), end.isoformat()),
            ).fetchone()
        return from_cents(int(row["cents"]))
