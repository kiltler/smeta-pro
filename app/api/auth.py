"""Вход по номеру телефона: запрос SMS-кода и обмен кода на JWT."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models import User
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


class PhoneIn(BaseModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def normalize(cls, v: str) -> str:
        try:
            return auth_service.normalize_phone(v)
        except auth_service.InvalidPhone:
            raise ValueError("Укажите российский мобильный номер, например +79141234567")


class VerifyIn(PhoneIn):
    code: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeOut(BaseModel):
    id: int
    phone: str


@router.post("/request-code")
def request_code(data: PhoneIn, db: Session = Depends(get_db)):
    try:
        auth_service.request_code(db, data.phone)
        db.commit()
    except auth_service.RateLimitExceeded:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Слишком много запросов кода. Попробуйте через час.",
        )
    return {"detail": "Код отправлен"}


@router.post("/verify", response_model=TokenOut)
def verify(data: VerifyIn, db: Session = Depends(get_db)):
    try:
        user = auth_service.verify_code(db, data.phone, data.code)
    except auth_service.InvalidCode:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный или истёкший код. Запросите новый.",
        )
    return TokenOut(access_token=auth_service.create_access_token(user.id))


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user)):
    """Текущий пользователь. Приватный роут — образец подключения авторизации."""
    return MeOut(id=user.id, phone=user.phone)
