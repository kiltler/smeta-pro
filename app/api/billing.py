"""Биллинг: состояние подписки, оплата Pro, отмена, вебхук ЮKassa."""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models import User
from app.services import billing

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/subscription")
def subscription(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return billing.subscription_state(db, user)


@router.post("/subscribe")
def subscribe(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        return {"confirmation_url": billing.start_subscription(db, user)}
    except billing.BillingNotConfigured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Оплата временно недоступна: магазин ЮKassa не настроен",
        )


@router.post("/cancel")
def cancel(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    billing.cancel_subscription(db, user)
    return billing.subscription_state(db, user)


@router.post("/resume")
def resume(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    billing.resume_subscription(db, user)
    return billing.subscription_state(db, user)


@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    """Вебхук ЮKassa. Без авторизации; подлинность обеспечивается тем,
    что данные платежа перечитываются из API ЮKassa, а не берутся из тела."""
    body = await request.json()
    event_type = body.get("event", "")
    payment_id = ((body.get("object") or {}).get("id")) or ""
    if not event_type.startswith("payment.") or not payment_id:
        raise HTTPException(status_code=400, detail="Некорректное событие")
    try:
        result = billing.handle_webhook(db, event_type, payment_id)
    except Exception:
        logger.exception("Ошибка обработки вебхука %s %s", event_type, payment_id)
        # 500 → ЮKassa повторит доставку; идемпотентность защитит от дублей
        raise HTTPException(status_code=500, detail="Ошибка обработки")
    return {"result": result}
