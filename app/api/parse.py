"""ИИ-парсинг диктовок: POST /parse и фиксация правок пользователя."""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models import User
from app.services import parser

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/parse", tags=["parse"])


class ParseIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class CorrectionIn(BaseModel):
    # Снапшот позиций после правки на экране проверки — формат тот же,
    # что в parsed_json (правило 9.6: формат parse_logs не менять)
    positions: list[dict]


@router.post("")
def parse(data: ParseIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        return parser.parse_text(db, user, data.text)
    except parser.ParserNotConfigured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ИИ-парсер не настроен: задайте ANTHROPIC_API_KEY в .env",
        )
    except Exception:
        logger.exception("Ошибка ИИ-парсинга")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Не удалось распознать текст. Попробуйте ещё раз или введите позиции вручную.",
        )


@router.put("/{log_id}")
def save_correction(
    log_id: int,
    data: CorrectionIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    log = parser.save_correction(db, user, log_id, data.model_dump())
    if log is None:
        raise HTTPException(status_code=404, detail="Запись парсинга не найдена")
    return {"detail": "Правка сохранена"}
