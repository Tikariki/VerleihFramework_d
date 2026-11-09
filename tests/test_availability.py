"""Tests zur Verfügbarkeit von Gegenständen."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.domain.errors import NotFoundError

FUTURE = date.today() + timedelta(days=30)


def test_status_neuer_gegenstand_ist_verfuegbar(container, make_item):
    item = make_item()
    assert container.items.get_item(item.id)["status"] == "available"


def test_verliehener_gegenstand_ist_nicht_verfuegbar(container, make_item, make_customer, make_rental):
    item = make_item()
    customer = make_customer()
    make_rental(item.id, customer.id, start=date.today(), days=2)

    assert container.items.get_item(item.id)["status"] == "rented"


def test_freie_gegenstaende_im_zeitraum_werden_korrekt_gefiltert(
    container, make_item, make_customer, make_rental
):
    belegt = make_item(name="Ski A")
    frei = make_item(name="Ski B")
    customer = make_customer()
    make_rental(belegt.id, customer.id, start=FUTURE, days=2)

    ids = {item["id"] for item in container.items.available_items(start=FUTURE, days=1)}

    assert belegt.id not in ids
    assert frei.id in ids


def test_zeitraum_nach_rueckgabetermin_ist_wieder_frei(
    container, make_item, make_customer, make_rental
):
    item = make_item()
    customer = make_customer()
    make_rental(item.id, customer.id, start=FUTURE, days=2)

    ids = {
        item["id"]
        for item in container.items.available_items(start=FUTURE + timedelta(days=3), days=1)
    }
    assert item.id in ids


def test_verleihfenster_ueberlappt_nicht_mit_anschluss(
    container, make_item, make_customer, make_rental
):
    item = make_item()
    customer = make_customer()
    rental = make_rental(item.id, customer.id, start=FUTURE, days=2)

    ids = {
        item["id"]
        for item in container.items.available_items(start=rental.due_date, days=1)
    }
    assert item.id in ids


def test_freie_gegenstaende_nach_typ_filterbar(container, make_item, make_customer, make_rental):
    ski = make_item(name="Ski A", type_key="ski")
    bike = make_item(
        name="Citybike",
        type_key="bike",
        attributes={"bike_kind": "City", "frame_size": "M"},
    )
    customer = make_customer()
    make_rental(ski.id, customer.id, start=FUTURE, days=1)

    items = container.items.available_items(start=FUTURE, days=1, type_key="bike")
    assert [item["id"] for item in items] == [bike.id]


def test_deaktivierter_gegenstand_erscheint_nicht_in_liste(container, make_item):
    item = make_item()
    container.items.update_item(item.id, {"active": False})

    assert container.items.list_items() == []
    assert len(container.items.list_items(include_inactive=True)) == 1
    assert container.items.get_item(item.id)["status"] == "inactive"


def test_loeschen_mit_historie_deaktiviert_statt_zu_loeschen(
    container, make_item, make_customer, make_rental
):
    item = make_item()
    customer = make_customer()
    make_rental(item.id, customer.id, start=FUTURE, days=1)

    result = container.items.delete_item(item.id)

    assert result["deleted"] is False
    assert result["deactivated"] is True
    assert container.items.get_item(item.id)["status"] == "inactive"


def test_loeschen_ohne_historie_entfernt_gegenstand(container, make_item):
    item = make_item()
    result = container.items.delete_item(item.id)

    assert result["deleted"] is True

    with pytest.raises(NotFoundError):
        container.items.get_item(item.id)
