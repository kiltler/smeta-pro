"""Документы владельца: смета из корзины, договор и акт из согласованной сметы,
история, PDF, дублирование, отметка оплаты."""
import re
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import storage
from app.api.deps import get_current_user
from app.db import get_db
from app.models import Document, User
from app.services import billing
from app.services import documents as doc_service

PAYWALL_DETAIL = (
    "Создано 3 документа в этом месяце. Pro снимает лимит — 790 ₽/мес"
)

router = APIRouter(prefix="/documents", tags=["documents"])


class PositionIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    unit: str = Field(min_length=1, max_length=20)
    price: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    qty: float = Field(gt=0)


class EstimateIn(BaseModel):
    positions: list[PositionIn] = Field(min_length=1)
    client_name: str | None = Field(default=None, max_length=200)


class ClientIn(BaseModel):
    """Заказчик для договора: физлицо (ФИО) или юрлицо (название + ИНН)."""

    type: Literal["person", "company"] = "person"
    name: str = Field(min_length=1, max_length=200)
    inn: str | None = None
    address: str = Field(min_length=1, max_length=300)
    phone: str = Field(min_length=1, max_length=30)

    @field_validator("inn")
    @classmethod
    def validate_inn(cls, v: str | None) -> str | None:
        if v is None or v.strip() == "":
            return None
        digits = re.sub(r"\D", "", v)
        if len(digits) not in (10, 12):
            raise ValueError("ИНН заказчика — 10 или 12 цифр")
        return digits

    @model_validator(mode="after")
    def company_needs_inn(self):
        if self.type == "company" and not self.inn:
            raise ValueError("Для юрлица укажите ИНН")
        return self


class ContractActIn(BaseModel):
    client: ClientIn
    # срок выполнения работ — строкой, как удобно мастеру («до 25.07.2026», «5 рабочих дней»)
    work_deadline: str = Field(min_length=1, max_length=120)


class DocumentOut(BaseModel):
    id: int
    type: Literal["estimate", "contract", "act"]
    status: Literal["draft", "sent", "approved", "paid"]
    client_name: str | None
    total: str
    public_uuid: str | None  # у договора и акта публичной ссылки нет
    created_at: str
    expires_at: str | None
    parent_id: int | None


class ContractActOut(BaseModel):
    contract: DocumentOut
    act: DocumentOut


def _to_out(d: Document) -> DocumentOut:
    client_name = d.payload.get("client_name") or (d.payload.get("client") or {}).get("name")
    return DocumentOut(
        id=d.id,
        type=d.type,
        status=d.status,
        client_name=client_name,
        total=d.payload.get("total", "0"),
        public_uuid=str(d.public_uuid) if d.public_uuid else None,
        created_at=d.created_at.isoformat(),
        expires_at=d.expires_at.isoformat() if d.expires_at else None,
        parent_id=d.parent_id,
    )


def _get_own(db: Session, user: User, doc_id: int) -> Document:
    document = db.get(Document, doc_id)
    if document is None or document.user_id != user.id:
        raise HTTPException(status_code=404, detail="Документ не найден")
    return document


def _check_limit_or_402(db: Session, user: User) -> None:
    try:
        billing.ensure_can_create_document(db, user)
    except billing.LimitExceeded:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=PAYWALL_DETAIL
        )


@router.post("/estimate", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def create_estimate(
    data: EstimateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    _check_limit_or_402(db, user)
    document = doc_service.create_estimate(
        db, user, [p.model_dump() for p in data.positions], data.client_name
    )
    billing.increment_usage(db, user)
    db.commit()
    return _to_out(document)


@router.get("", response_model=list[DocumentOut])
def list_documents(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    docs = db.scalars(
        select(Document).where(Document.user_id == user.id).order_by(Document.id.desc())
    ).all()
    return [_to_out(d) for d in docs]


@router.get("/{doc_id}/pdf")
def get_pdf(doc_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    document = _get_own(db, user, doc_id)
    if not document.pdf_key:
        raise HTTPException(status_code=404, detail="PDF не сгенерирован")
    data, content_type = storage.get_object(document.pdf_key)
    return Response(
        content=data,
        media_type=content_type,
        headers={"Content-Disposition": f'inline; filename="smeta-{document.id}.pdf"'},
    )


@router.post("/{doc_id}/contract-act", response_model=ContractActOut, status_code=201)
def create_contract_act(
    doc_id: int,
    data: ContractActIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    estimate = _get_own(db, user, doc_id)
    if estimate.type != "estimate":
        raise HTTPException(status_code=400, detail="Договор и акт создаются из сметы")
    if estimate.status not in ("approved", "paid"):
        raise HTTPException(
            status_code=400,
            detail="Сначала клиент должен согласовать смету по публичной ссылке",
        )
    existing = db.scalar(select(Document).where(Document.parent_id == estimate.id))
    if existing is not None:
        raise HTTPException(
            status_code=409, detail="Договор и акт по этой смете уже созданы"
        )
    contract, act = doc_service.create_contract_and_act(
        db, user, estimate, data.client.model_dump(), data.work_deadline
    )
    return ContractActOut(contract=_to_out(contract), act=_to_out(act))


@router.post("/{doc_id}/mark-paid", response_model=DocumentOut)
def mark_paid(doc_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Отметка «оплачено». Фронт после неё напоминает про чек в «Мой налог»."""
    document = _get_own(db, user, doc_id)
    if document.type != "estimate":
        raise HTTPException(status_code=400, detail="Оплата отмечается на смете")
    if document.status not in ("approved", "paid"):
        raise HTTPException(
            status_code=400, detail="Отметить оплату можно после согласования сметы"
        )
    if document.status != "paid":
        document.status = "paid"
        db.commit()
    return _to_out(document)


@router.post("/{doc_id}/duplicate", response_model=DocumentOut, status_code=201)
def duplicate(doc_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    source = _get_own(db, user, doc_id)
    if source.type != "estimate":
        raise HTTPException(status_code=400, detail="Дублировать можно только смету")
    _check_limit_or_402(db, user)
    document = doc_service.duplicate_estimate(db, user, source)
    billing.increment_usage(db, user)
    db.commit()
    return _to_out(document)
