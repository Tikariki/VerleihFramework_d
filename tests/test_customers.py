"""Tests der Kunden- und Ausweisverwaltung."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.domain.errors import ConflictError, NotFoundError, ValidationError

FUTURE = date.today() + timedelta(days=30)


def test_kunde_mit_ausweis_anlegen(container, make_customer):
    customer = make_customer(first_name="Lena", last_name="Huber")

    payload = container.customers.get_customer(customer.id)
    assert payload["full_name"] == "Lena Huber"
    assert payload["has_id_document"] is True
    assert payload["id_document"]["type_key"] == "id_card"
    assert payload["id_document"]["number"] == "AT-123456789"


def test_kunde_ohne_ausweis_ist_erlaubt(container, make_customer):
    customer = make_customer(with_document=False)
    payload = container.customers.get_customer(customer.id)

    assert payload["has_id_document"] is False
    assert payload["id_document"] is None


def test_leerer_vorname_wird_abgelehnt(container):
    with pytest.raises(ValidationError):
        container.customers.create_customer({"first_name": "  ", "last_name": "Test"})


def test_ungueltige_email_wird_abgelehnt(container):
    with pytest.raises(ValidationError):
        container.customers.create_customer(
            {"first_name": "Max", "last_name": "Test", "email": "keine-mail"}
        )


def test_unbekannter_ausweistyp_wird_abgelehnt(container, make_customer):
    customer = make_customer(with_document=False)
    with pytest.raises(ValidationError):
        container.customers.attach_document(
            customer.id, type_key="raumfahrt_pass", number="X-1"
        )


def test_ausweisnummer_ist_pflicht(container, make_customer):
    customer = make_customer(with_document=False)
    with pytest.raises(ValidationError):
        container.customers.attach_document(customer.id, type_key="passport", number="  ")


def test_ausweis_kann_nachgereicht_werden(container, make_customer, make_item, make_rental):
    customer = make_customer(with_document=False)
    item = make_item()

    container.customers.attach_document(
        customer.id, type_key="passport", number="P-998877", file_name="scan.pdf"
    )
    payload = container.customers.get_customer(customer.id)
    assert payload["id_document"]["type_key"] == "passport"
    assert payload["id_document"]["file_name"] == "scan.pdf"

    rental = make_rental(item.id, customer.id, start=FUTURE, days=1)
    assert rental.id is not None


def test_update_behaelt_ausweis(container, make_customer):
    customer = make_customer()
    container.customers.update_customer(customer.id, {"phone": "+43 660 1234567"})

    payload = container.customers.get_customer(customer.id)
    assert payload["phone"] == "+43 660 1234567"
    assert payload["id_document"]["number"] == "AT-123456789"


def test_kunde_mit_verleih_kann_nicht_geloescht_werden(
    container, make_customer, make_item, make_rental
):
    customer = make_customer()
    item = make_item()
    make_rental(item.id, customer.id, start=FUTURE, days=1)

    with pytest.raises(ConflictError):
        container.customers.delete_customer(customer.id)


def test_kunde_ohne_verleih_kann_geloescht_werden(container, make_customer):
    customer = make_customer()
    container.customers.delete_customer(customer.id)

    with pytest.raises(NotFoundError):
        container.customers.get_customer(customer.id)


def test_kundenliste_zeigt_aktive_verleihe(container, make_customer, make_item, make_rental):
    customer = make_customer()
    other = make_customer(first_name="Tom", last_name="Neu")
    item = make_item()
    make_rental(item.id, customer.id, start=date.today(), days=1)

    by_name = {entry["full_name"]: entry for entry in container.customers.list_customers()}
    assert by_name["Anna Müller"]["has_active_rental"] is True
    assert by_name["Tom Neu"]["has_active_rental"] is False
