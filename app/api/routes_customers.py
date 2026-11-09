"""HTTP-Endpunkte für Kunden und Ausweise."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, UploadFile, status

from ..domain.errors import ValidationError
from .deps import ContainerDep
from .schemas import CustomerIn, CustomerUpdate, MessageOut

router = APIRouter(prefix="/api/customers", tags=["Kunden"])

ALLOWED_UPLOAD_SUFFIXES = {".jpg", ".jpeg", ".png", ".pdf"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


@router.get("", summary="Kunden auflisten")
def list_customers(container: ContainerDep) -> dict:
    return {"customers": container.customers.list_customers()}


@router.get("/{customer_id}", summary="Kunde inkl. Verleihhistorie")
def get_customer(customer_id: int, container: ContainerDep) -> dict:
    return container.customers.get_customer(customer_id)


@router.post("", status_code=status.HTTP_201_CREATED, summary="Kunde anlegen")
def create_customer(payload: CustomerIn, container: ContainerDep) -> dict:
    customer = container.customers.create_customer(payload.model_dump())
    return container.customers.get_customer(customer.id)


@router.put("/{customer_id}", summary="Kunde bearbeiten")
def update_customer(customer_id: int, payload: CustomerUpdate, container: ContainerDep) -> dict:
    data = {key: value for key, value in payload.model_dump().items() if value is not None}
    container.customers.update_customer(customer_id, data)
    return container.customers.get_customer(customer_id)


@router.delete("/{customer_id}", response_model=MessageOut, summary="Kunde löschen")
def delete_customer(customer_id: int, container: ContainerDep) -> dict:
    container.customers.delete_customer(customer_id)
    return {"message": "Kunde gelöscht.", "deleted": True}


@router.post("/{customer_id}/document", summary="Ausweis hochladen oder ersetzen")
async def upload_document(
    customer_id: int,
    container: ContainerDep,
    type_key: str = Form(...),
    number: str = Form(""),
    file: UploadFile | None = File(default=None),
) -> dict:
    stored_name: str | None = None

    if file is not None and file.filename:
        suffix = Path(file.filename).suffix.lower()
        if suffix not in ALLOWED_UPLOAD_SUFFIXES:
            raise ValidationError(
                "Nur JPG, PNG oder PDF können hochgeladen werden."
            )
        content = await file.read()
        if len(content) > MAX_UPLOAD_BYTES:
            raise ValidationError("Die Datei darf höchstens 5 MB groß sein.")
        stored_name = f"ausweis_{customer_id}_{uuid4().hex}{suffix}"
        (container.settings.upload_dir / stored_name).write_bytes(content)

    container.customers.attach_document(
        customer_id, type_key=type_key, number=number, file_name=stored_name
    )
    return container.customers.get_customer(customer_id)
