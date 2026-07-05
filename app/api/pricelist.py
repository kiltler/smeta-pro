"""Прайс-лист: CRUD позиций и заполнение шаблоном «кондиционерщик»."""
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models import Bundle, PriceItem, User
from app.services.hvac_template import seed_hvac

router = APIRouter(prefix="/pricelist", tags=["pricelist"])


class ItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    unit: str = Field(min_length=1, max_length=20)
    price: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    synonyms: list[str] = []
    niche: str = "hvac"
    sort: int = 0


class ItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    unit: str | None = Field(default=None, min_length=1, max_length=20)
    price: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    synonyms: list[str] | None = None
    sort: int | None = None


class ItemOut(ItemIn):
    id: int


def _to_out(item: PriceItem) -> ItemOut:
    return ItemOut(
        id=item.id,
        name=item.name,
        unit=item.unit,
        price=item.price,
        synonyms=item.synonyms or [],
        niche=item.niche,
        sort=item.sort,
    )


def _get_own_item(db: Session, user: User, item_id: int) -> PriceItem:
    item = db.get(PriceItem, item_id)
    if item is None or item.user_id != user.id:
        raise HTTPException(status_code=404, detail="Позиция не найдена")
    return item


@router.get("", response_model=list[ItemOut])
def list_items(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.scalars(
        select(PriceItem)
        .where(PriceItem.user_id == user.id)
        .order_by(PriceItem.sort, PriceItem.id)
    ).all()
    return [_to_out(i) for i in items]


@router.post("", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
def create_item(
    data: ItemIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    item = PriceItem(user_id=user.id, **data.model_dump())
    db.add(item)
    db.commit()
    return _to_out(item)


@router.put("/{item_id}", response_model=ItemOut)
def update_item(
    item_id: int,
    data: ItemUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = _get_own_item(db, user, item_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    return _to_out(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    item = _get_own_item(db, user, item_id)
    # Убираем позицию из комплектов, чтобы не оставлять битые ссылки
    bundles = db.scalars(select(Bundle).where(Bundle.user_id == user.id)).all()
    for bundle in bundles:
        filtered = [p for p in bundle.items if p.get("price_item_id") != item_id]
        if len(filtered) != len(bundle.items):
            bundle.items = filtered
    db.delete(item)
    db.commit()


@router.post("/seed")
def seed_template(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Заполняет прайс шаблоном «кондиционерщик». Если прайс уже есть — ничего не делает."""
    try:
        items, bundles = seed_hvac(db, user.id)
    except RuntimeError:
        return {"created": False, "detail": "Прайс уже заполнен"}
    db.commit()
    return {"created": True, "items": items, "bundles": bundles}
