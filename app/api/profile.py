"""Профиль пользователя: бренд, реквизиты, логотип (через app/storage.py)."""
import logging
import uuid

import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status
from minio.error import S3Error
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app import storage
from app.api.deps import get_current_user
from app.db import get_db
from app.models import Profile, User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/profile", tags=["profile"])

MAX_LOGO_SIZE = 2 * 1024 * 1024  # 2 МБ
ALLOWED_LOGO_TYPES = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/svg+xml": "svg",
}


class ThemeIn(BaseModel):
    theme: Literal["light", "dark", "system"]


class ProfileIn(BaseModel):
    brand_name: str | None = Field(default=None, max_length=200)
    full_name: str | None = Field(default=None, max_length=200)
    inn: str | None = None
    requisites: dict = {}

    @field_validator("inn")
    @classmethod
    def validate_inn(cls, v: str | None) -> str | None:
        if v is None or v.strip() == "":
            return None
        digits = re.sub(r"\D", "", v)
        if len(digits) not in (10, 12):
            raise ValueError(
                "ИНН — это 10 цифр (организация) или 12 цифр (ИП/самозанятый). "
                f"У вас {len(digits)}."
            )
        return digits


class ProfileOut(ProfileIn):
    has_logo: bool = False
    theme: str = "dark"


def _get_or_create(db: Session, user_id: int) -> Profile:
    profile = db.get(Profile, user_id)
    if profile is None:
        profile = Profile(user_id=user_id)
        db.add(profile)
    return profile


@router.get("", response_model=ProfileOut)
def get_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.get(Profile, user.id)
    if profile is None:
        return ProfileOut()
    return ProfileOut(
        brand_name=profile.brand_name,
        full_name=profile.full_name,
        inn=profile.inn,
        requisites=profile.requisites or {},
        has_logo=profile.logo_key is not None,
        theme=profile.theme or "dark",
    )


@router.put("", response_model=ProfileOut)
def update_profile(
    data: ProfileIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    profile = _get_or_create(db, user.id)
    profile.brand_name = data.brand_name
    profile.full_name = data.full_name
    profile.inn = data.inn
    profile.requisites = data.requisites
    db.commit()
    return ProfileOut(
        **data.model_dump(),
        has_logo=profile.logo_key is not None,
        theme=profile.theme or "dark",
    )


@router.put("/theme")
def set_theme(
    data: ThemeIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Тема интерфейса хранится в профиле (доступна с любого устройства)."""
    profile = _get_or_create(db, user.id)
    profile.theme = data.theme
    db.commit()
    return {"theme": data.theme}


@router.post("/logo")
def upload_logo(
    file: UploadFile, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    ext = ALLOWED_LOGO_TYPES.get(file.content_type)
    if ext is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Логотип — картинка PNG, JPEG, WebP или SVG",
        )
    data = file.file.read(MAX_LOGO_SIZE + 1)
    if len(data) > MAX_LOGO_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Файл больше 2 МБ. Уменьшите картинку.",
        )

    profile = _get_or_create(db, user.id)
    old_key = profile.logo_key
    key = f"logos/{user.id}/{uuid.uuid4().hex}.{ext}"
    storage.put_object(key, data, file.content_type)
    profile.logo_key = key
    db.commit()

    if old_key:
        try:
            storage.remove_object(old_key)
        except Exception:
            logger.warning("Не удалось удалить старый логотип %s", old_key)
    return {"detail": "Логотип загружен"}


@router.get("/logo")
def get_logo(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.get(Profile, user.id)
    if profile is None or profile.logo_key is None:
        raise HTTPException(status_code=404, detail="Логотип не загружен")
    try:
        data, content_type = storage.get_object(profile.logo_key)
    except S3Error:
        raise HTTPException(status_code=404, detail="Логотип не найден в хранилище")
    return Response(content=data, media_type=content_type)
