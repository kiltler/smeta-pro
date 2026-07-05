"""Комплекты: конструктор наборов позиций прайса с количеством по умолчанию."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models import Bundle, PriceItem, User

router = APIRouter(prefix="/bundles", tags=["bundles"])


class BundlePart(BaseModel):
    price_item_id: int
    qty_default: float = Field(gt=0)
    ask_qty: bool = False


class BundleIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    items: list[BundlePart] = Field(min_length=1)
    sort: int = 0


class BundleOut(BundleIn):
    id: int


def _validate_parts(db: Session, user: User, parts: list[BundlePart]) -> None:
    ids = {p.price_item_id for p in parts}
    owned = set(
        db.scalars(
            select(PriceItem.id).where(PriceItem.user_id == user.id, PriceItem.id.in_(ids))
        ).all()
    )
    missing = ids - owned
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Позиции не найдены в вашем прайсе: {sorted(missing)}",
        )


def _get_own_bundle(db: Session, user: User, bundle_id: int) -> Bundle:
    bundle = db.get(Bundle, bundle_id)
    if bundle is None or bundle.user_id != user.id:
        raise HTTPException(status_code=404, detail="Комплект не найден")
    return bundle


def _to_out(bundle: Bundle) -> BundleOut:
    return BundleOut(
        id=bundle.id,
        name=bundle.name,
        sort=bundle.sort,
        items=[BundlePart(**p) for p in bundle.items],
    )


@router.get("", response_model=list[BundleOut])
def list_bundles(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bundles = db.scalars(
        select(Bundle).where(Bundle.user_id == user.id).order_by(Bundle.sort, Bundle.id)
    ).all()
    return [_to_out(b) for b in bundles]


@router.post("", response_model=BundleOut, status_code=status.HTTP_201_CREATED)
def create_bundle(
    data: BundleIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    _validate_parts(db, user, data.items)
    bundle = Bundle(
        user_id=user.id,
        name=data.name,
        sort=data.sort,
        items=[p.model_dump() for p in data.items],
    )
    db.add(bundle)
    db.commit()
    return _to_out(bundle)


@router.put("/{bundle_id}", response_model=BundleOut)
def update_bundle(
    bundle_id: int,
    data: BundleIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bundle = _get_own_bundle(db, user, bundle_id)
    _validate_parts(db, user, data.items)
    bundle.name = data.name
    bundle.sort = data.sort
    bundle.items = [p.model_dump() for p in data.items]
    db.commit()
    return _to_out(bundle)


@router.delete("/{bundle_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bundle(
    bundle_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    bundle = _get_own_bundle(db, user, bundle_id)
    db.delete(bundle)
    db.commit()
