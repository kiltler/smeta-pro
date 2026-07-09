"""Документы владельца: создание сметы из корзины, история, PDF, дублирование."""
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import storage
from app.api.deps import get_current_user
from app.db import get_db
from app.models import Document, User
from app.services import documents as doc_service

router = APIRouter(prefix="/documents", tags=["documents"])


class PositionIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    unit: str = Field(min_length=1, max_length=20)
    price: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    qty: float = Field(gt=0)


class EstimateIn(BaseModel):
    positions: list[PositionIn] = Field(min_length=1)
    client_name: str | None = Field(default=None, max_length=200)


class DocumentOut(BaseModel):
    id: int
    type: Literal["estimate", "contract", "act"]
    status: Literal["draft", "sent", "approved"]
    client_name: str | None
    total: str
    public_uuid: str
    created_at: str
    expires_at: str | None
    parent_id: int | None


def _to_out(d: Document) -> DocumentOut:
    return DocumentOut(
        id=d.id,
        type=d.type,
        status=d.status,
        client_name=d.payload.get("client_name"),
        total=d.payload.get("total", "0"),
        public_uuid=str(d.public_uuid),
        created_at=d.created_at.isoformat(),
        expires_at=d.expires_at.isoformat() if d.expires_at else None,
        parent_id=d.parent_id,
    )


def _get_own(db: Session, user: User, doc_id: int) -> Document:
    document = db.get(Document, doc_id)
    if document is None or document.user_id != user.id:
        raise HTTPException(status_code=404, detail="Документ не найден")
    return document


@router.post("/estimate", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def create_estimate(
    data: EstimateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    document = doc_service.create_estimate(
        db, user, [p.model_dump() for p in data.positions], data.client_name
    )
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


@router.post("/{doc_id}/duplicate", response_model=DocumentOut, status_code=201)
def duplicate(doc_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    source = _get_own(db, user, doc_id)
    if source.type != "estimate":
        raise HTTPException(status_code=400, detail="Дублировать можно только смету")
    return _to_out(doc_service.duplicate_estimate(db, user, source))
