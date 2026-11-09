"""Tests der HTTP-Schnittstelle."""

from __future__ import annotations

from datetime import date, timedelta

FUTURE = (date.today() + timedelta(days=20)).isoformat()


def _create_ski(client, name="Atomic Redster 170", daily_rate=25.0, category="Standard"):
    response = client.post(
        "/api/items",
        json={
            "type_key": "ski",
            "name": name,
            "category": category,
            "daily_rate": daily_rate,
            "attributes": {"length_cm": 170, "skill_level": "Fortgeschritten"},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_customer(client, first="Anna", last="Müller"):
    response = client.post(
        "/api/customers",
        json={
            "first_name": first,
            "last_name": last,
            "email": "anna@example.com",
            "id_type": "id_card",
            "id_number": "AT-123456",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_meta_liefert_verleiharten_und_regeln(client):
    data = client.get("/api/meta").json()
    type_keys = {entry["type_key"] for entry in data["item_types"]}
    assert {"ski", "snowboard", "bike"} <= type_keys
    assert any(rule["key"] == "duration" for rule in data["pricing_rules"])
    assert any(doc["key"] == "passport" for doc in data["id_document_types"])


def test_dashboard_seite_wird_ausgeliefert(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "VerleihFramework" in response.text


def test_gegenstand_anlegen_und_auflisten(client):
    item = _create_ski(client)
    assert item["name"] == "Atomic Redster 170"

    items = client.get("/api/items").json()["items"]
    assert len(items) == 1
    assert items[0]["name"] == "Atomic Redster 170"
    assert items[0]["status"] == "available"
    assert items[0]["type_label"] == "Ski"


def test_gegenstand_mit_ungueltigem_typ_wird_abgelehnt(client):
    response = client.post(
        "/api/items",
        json={"type_key": "hovercraft", "name": "X", "category": "Standard", "daily_rate": 10},
    )
    assert response.status_code == 422
    assert "hovercraft" in response.json()["message"]


def test_gegenstand_bearbeiten(client):
    item = _create_ski(client)
    response = client.put(f"/api/items/{item['id']}", json={"daily_rate": 30.0})
    assert response.status_code == 200
    assert response.json()["daily_rate"] == "30.00"


def test_gegenstand_loeschen(client):
    item = _create_ski(client)
    response = client.delete(f"/api/items/{item['id']}")
    assert response.status_code == 200
    assert response.json()["deleted"] is True
    assert client.get("/api/items").json()["items"] == []


def test_unbekannter_gegenstand_gibt_404(client):
    response = client.get("/api/items/999")
    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def test_kunde_anlegen_und_ausweis_hochladen(client):
    customer = _create_customer(client)
    assert customer["has_id_document"] is True

    response = client.post(
        f"/api/customers/{customer['id']}/document",
        data={"type_key": "passport", "number": "P-778899"},
        files={"file": ("ausweis.pdf", b"%PDF-1.4 test", "application/pdf")},
    )
    assert response.status_code == 200
    document = response.json()["id_document"]
    assert document["type_key"] == "passport"
    assert document["number"] == "P-778899"
    assert document["file_name"].endswith(".pdf")


def test_ungueltiger_dateityp_wird_abgelehnt(client):
    customer = _create_customer(client)
    response = client.post(
        f"/api/customers/{customer['id']}/document",
        data={"type_key": "id_card", "number": "AT-1"},
        files={"file": ("virus.exe", b"MZ", "application/octet-stream")},
    )
    assert response.status_code == 422


def test_verleih_anlegen_und_zurueckgeben(client):
    item = _create_ski(client)
    customer = _create_customer(client)

    created = client.post(
        "/api/rentals",
        json={
            "item_id": item["id"],
            "customer_id": customer["id"],
            "start_date": FUTURE,
            "days": 3,
        },
    )
    assert created.status_code == 201, created.text
    rental = created.json()
    assert rental["status"] == "active"
    assert rental["total"] == "75.00"

    returned = client.post(f"/api/rentals/{rental['id']}/return")
    assert returned.status_code == 200
    assert returned.json()["status"] == "returned"

    assert client.get("/api/items").json()["items"][0]["status"] == "available"


def test_preisvorschau_ohne_buchung(client):
    item = _create_ski(client)
    customer = _create_customer(client)

    response = client.post(
        "/api/rentals/quote",
        json={"item_id": item["id"], "customer_id": customer["id"], "days": 7},
    )
    assert response.status_code == 200
    quote = response.json()
    assert quote["total"] == "140.00"
    assert len(quote["lines"]) == 2
    # Vorschau darf keinen Verleih anlegen
    assert client.get("/api/rentals").json()["rentals"] == []


def test_doppelter_verleih_gibt_409(client):
    item = _create_ski(client)
    customer = _create_customer(client)
    payload = {
        "item_id": item["id"],
        "customer_id": customer["id"],
        "start_date": FUTURE,
        "days": 2,
    }
    assert client.post("/api/rentals", json=payload).status_code == 201

    conflict = client.post("/api/rentals", json=payload)
    assert conflict.status_code == 409
    assert conflict.json()["error"] == "item_unavailable"


def test_verleih_ohne_ausweis_gibt_409(client):
    item = _create_ski(client)
    customer = client.post(
        "/api/customers", json={"first_name": "Ohne", "last_name": "Ausweis"}
    ).json()

    response = client.post(
        "/api/rentals",
        json={
            "item_id": item["id"],
            "customer_id": customer["id"],
            "start_date": FUTURE,
            "days": 1,
        },
    )
    assert response.status_code == 409


def test_ungueltige_dauer_gibt_422(client):
    item = _create_ski(client)
    customer = _create_customer(client)

    response = client.post(
        "/api/rentals",
        json={"item_id": item["id"], "customer_id": customer["id"], "days": 0},
    )
    assert response.status_code == 422


def test_verleih_filter_nach_status(client):
    item = _create_ski(client)
    customer = _create_customer(client)
    rental = client.post(
        "/api/rentals",
        json={
            "item_id": item["id"],
            "customer_id": customer["id"],
            "start_date": FUTURE,
            "days": 1,
        },
    ).json()

    assert len(client.get("/api/rentals?status=active").json()["rentals"]) == 1
    assert client.get("/api/rentals?status=returned").json()["rentals"] == []

    client.post(f"/api/rentals/{rental['id']}/return")

    assert client.get("/api/rentals?status=active").json()["rentals"] == []
    assert len(client.get("/api/rentals?status=returned").json()["rentals"]) == 1


def test_dashboard_kennzahlen(client):
    item = _create_ski(client)
    customer = _create_customer(client)
    client.post(
        "/api/rentals",
        json={
            "item_id": item["id"],
            "customer_id": customer["id"],
            "start_date": date.today().isoformat(),
            "days": 2,
        },
    )

    data = client.get("/api/dashboard").json()

    assert data["items"]["rented"] == 1
    assert data["items"]["available"] == 0
    assert data["rentals"]["active"] == 1
    assert data["customers"]["total"] == 1
    assert _as_float(data["revenue"]["month"]) == 50.0


def test_freie_gegenstaende_endpunkt(client):
    item = _create_ski(client)
    customer = _create_customer(client)
    client.post(
        "/api/rentals",
        json={
            "item_id": item["id"],
            "customer_id": customer["id"],
            "start_date": FUTURE,
            "days": 2,
        },
    )

    busy = client.get(f"/api/items/available?start={FUTURE}&days=1").json()["items"]
    free = client.get(f"/api/items/available?start=2027-06-01&days=1").json()["items"]

    assert busy == []
    assert len(free) == 1


def test_openapi_dokumentation_ist_erreichbar(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/api/rentals" in response.json()["paths"]


def _as_float(value) -> float:
    """Vergleicht Geldbeträge als Zahl (die API liefert Strings)."""
    return float(value)
