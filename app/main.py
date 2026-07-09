"""Точка входа приложения «СметаПро»."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import storage
from app.api import auth, bundles, documents, health, parse, pricelist, profile, public

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Готовим бакет в хранилище; если оно ещё не поднялось — не падаем,
    # /health честно покажет "storage": "fail".
    try:
        storage.ensure_bucket()
    except Exception:
        logger.exception("Не удалось подготовить бакет при старте")
    yield


app = FastAPI(title="СметаПро", lifespan=lifespan)
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(pricelist.router)
app.include_router(bundles.router)
app.include_router(parse.router)
app.include_router(documents.router)
app.include_router(public.router)
