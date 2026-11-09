"""HTTP-Endpunkte für Verleih und Rückgabe."""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from .deps import ContainerDep
from .schemas import RentalIn

router = APIRouter(prefix="/api/rentals", tags=["Verleihvorgänge"])


@router.get("", summary="Verleihvorgänge auflisten")
def list_rentals(
    container: ContainerDep,
    status_filter: str | None = Query(default=None, alias="status"),
    item_id: int | None = None,
    customer_id: int | None = None,
    limit: int | None = None,
) -> dict:
    return {
        "rentals": container.rentals.list_rentals(
            status=status_filter,
            item_id=item_id,
            customer_id=customer_id,
            limit=limit,
        )
    }


@router.get("/{rental_id}", summary="Verleihvorgang anzeigen")
def get_rental(rental_id: int, container: ContainerDep) -> dict:
    return container.rentals.get_rental(rental_id)


@router.post("/quote", summary="Preis berechnen, ohne zu buchen")
def quote(payload: RentalIn, container: ContainerDep) -> dict:
    return container.rentals.quote(payload.model_dump()).to_dict()


@router.post("", status_code=status.HTTP_201_CREATED, summary="Verleihvorgang anlegen")
def create_rental(payload: RentalIn, container: ContainerDep) -> dict:
    return container.rentals.create_rental(payload.model_dump()).to_dict()


@router.post("/{rental_id}/return", summary="Gegenstand zurücknehmen")
def return_rental(rental_id: int, container: ContainerDep) -> dict:
    return container.rentals.return_rental(rental_id).to_dict()
