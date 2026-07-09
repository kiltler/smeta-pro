"""GET /health — проверка живости сервиса; GET /config — публичные фиче-флаги."""
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import settings
from app.db import check_db
from app.storage import check_storage

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/config")
def public_config():
    """Публичные фиче-флаги для фронтенда (без секретов!)."""
    return {"parse_enabled": settings.parse_enabled}


@router.get("/health")
def health() -> JSONResponse:
    checks: dict[str, str] = {}

    try:
        check_db()
        checks["db"] = "ok"
    except Exception:
        logger.exception("Health-check: БД недоступна")
        checks["db"] = "fail"

    try:
        check_storage()
        checks["storage"] = "ok"
    except Exception:
        logger.exception("Health-check: хранилище недоступно")
        checks["storage"] = "fail"

    healthy = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "ok" if healthy else "fail", **checks},
    )
