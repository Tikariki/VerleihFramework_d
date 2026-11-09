"""Tests der Verleih- und Rückgabeprozesse."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.domain.errors import ConflictError, ItemUnavailableError, NotFoundError

# Fester Bezugspunkt in der Zukunft, damit Statuswerte unabhängig vom
# heutigen Datum deterministisch bleiben.
FUTURE = date.today() + timedelta(days=30)


def test_verleih_anlegen(container, make_item, make_customer, make_rental):
    item = make_item(daily_rate="25.00")
    customer = make_customer()
    rental = make_rental(item.id, customer.id, start=FUTURE, days=2)

    assert rental.id is not None
    assert rental.total == Decimal("50.00")
    assert rental.status == "active"
    assert rental.due_date == FUTURE + timedelta(days=2)
    assert rental.customer_name == "Anna Müller"
    assert rental.item_name == "Atomic Redster 170"


def test_verleih_speichert_preispositionen(container, make_item, make_customer, make_rental):
    item = make_item(daily_rate="25.00")
    customer = make_customer()
    rental = make_rental(item.id, customer.id, start=FUTURE, days=4)

    labels = [line["label"] for line in rental.price_lines]
    assert any("Tag(e)" in label for label in labels)
    assert any("Langzeitrabatt" in label for label in labels)
    assert rental.total == Decimal("90.00")


def test_gegenstand_gilt_nach_verleih_als_verliehen(container, make_item, make_customer, make_rental):
    item = make_item()
    customer = make_customer()
    make_rental(item.id, customer.id, start=date.today(), days=1)

    payload = container.items.get_item(item.id)
    assert payload["status"] == "rented"


def test_zweiter_verleih_im_gleichen_zeitraum_wird_abgelehnt(
    container, make_item, make_customer, make_rental
):
    item = make_item()
    customer = make_customer()
    make_rental(item.id, customer.id, start=FUTURE, days=3)

    with pytest.raises(ItemUnavailableError):
        make_rental(item.id, customer.id, start=FUTURE + timedelta(days=1), days=1)


def test_anschliessender_verleih_ist_erlaubt(container, make_item, make_customer, make_rental):
    item = make_item()
    customer = make_customer()
    first = make_rental(item.id, customer.id, start=FUTURE, days=3)
    second = make_rental(item.id, customer.id, start=first.due_date, days=1)

    assert second.id != first.id


def test_rueckgabe_setzt_status_und_gibt_gegenstand_frei(
    container, make_item, make_customer, make_rental
):
    item = make_item()
    customer = make_customer()
    rental = make_rental(item.id, customer.id, start=date.today(), days=1)

    returned = container.rentals.return_rental(rental.id)

    assert returned.status == "returned"
    assert returned.returned_at is not None
    assert container.items.get_item(item.id)["status"] == "available"


def test_doppelte_rueckgabe_wird_abgelehnt(container, make_item, make_customer, make_rental):
    item = make_item()
    customer = make_customer()
    rental = make_rental(item.id, customer.id, start=date.today(), days=1)
    container.rentals.return_rental(rental.id)

    with pytest.raises(ConflictError):
        container.rentals.return_rental(rental.id)


def test_verleih_ohne_ausweis_wird_abgelehnt(
    container, make_item, make_customer, make_rental
):
    item = make_item()
    customer = make_customer(with_document=False)

    with pytest.raises(ConflictError):
        make_rental(item.id, customer.id, start=FUTURE, days=1)


def test_deaktivierter_gegenstand_kann_nicht_verliehen_werden(
    container, make_item, make_customer, make_rental
):
    item = make_item()
    customer = make_customer()
    container.items.update_item(item.id, {"active": False})

    with pytest.raises(ItemUnavailableError):
        make_rental(item.id, customer.id, start=FUTURE, days=1)


def test_unbekannter_gegenstand_wirft_not_found(container, make_customer):
    customer = make_customer()
    with pytest.raises(NotFoundError):
        container.rentals.create_rental(
            {"item_id": 999, "customer_id": customer.id, "days": 1}
        )


def test_ueberfaelliger_verleih_wird_erkannt(container, make_item, make_customer, make_rental):
    item = make_item()
    customer = make_customer()
    rental = make_rental(item.id, customer.id, start=date.today() - timedelta(days=10), days=2)

    assert rental.is_overdue()
    assert rental.status == "overdue"
    assert container.rentals.list_rentals(status="overdue")[0]["id"] == rental.id


def test_verleihhistorie_nach_status(container, make_item, make_customer, make_rental):
    item = make_item()
    customer = make_customer()
    active = make_rental(item.id, customer.id, start=FUTURE, days=2)
    returned = make_rental(item.id, customer.id, start=FUTURE + timedelta(days=40), days=2)
    container.rentals.return_rental(returned.id)

    assert [r["id"] for r in container.rentals.list_rentals(status="active")] == [active.id]
    assert [r["id"] for r in container.rentals.list_rentals(status="returned")] == [returned.id]
    assert len(container.rentals.list_rentals()) == 2


def test_rueckgabeprozess_erzeugt_korrekte_historie(container, make_item, make_customer, make_rental):
    item = make_item()
    customer = make_customer()
    rental = make_rental(item.id, customer.id, start=FUTURE, days=2)
    container.rentals.return_rental(rental.id)

    history = container.customers.get_customer(customer.id)["history"]
    assert len(history) == 1
    assert history[0]["status"] == "returned"
