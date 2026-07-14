"""Публичные страницы для клиента (без регистрации): /e/{uuid}.

Ссылка неугадываемая (uuid4), живёт столько же, сколько смета (14 дней).
Первое открытие переводит смету draft → sent («клиент посмотрел»),
кнопка «Согласовать» — sent → approved (идемпотентно).
"""
import uuid as uuid_module

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import storage
from app.db import get_db
from app.models import Document, Profile
from app.services import documents as doc_service
from app.services import og_card

router = APIRouter(prefix="/e", tags=["public"])

EXPIRED_PAGE = """<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Срок сметы истёк</title>
<style>body{font-family:system-ui,sans-serif;background:#f4f6fa;color:#17212b;
display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
.card{background:#fff;border-radius:14px;padding:32px;max-width:420px;text-align:center}</style>
</head><body><div class="card"><h1>Срок действия сметы истёк</h1>
<p>Эта смета была действительна 14 дней. Свяжитесь с исполнителем —
он пришлёт актуальную версию.</p></div></body></html>"""


def _get_document(db: Session, public_uuid: str) -> Document:
    try:
        parsed = uuid_module.UUID(public_uuid)
    except ValueError:
        raise HTTPException(status_code=404, detail="Смета не найдена")
    document = db.scalar(select(Document).where(Document.public_uuid == parsed))
    if document is None:
        raise HTTPException(status_code=404, detail="Смета не найдена")
    if doc_service.is_expired(document):
        raise HTTPException(status_code=410, detail="expired")
    return document


@router.get("/{public_uuid}", response_class=HTMLResponse)
def public_estimate(public_uuid: str, request: Request, db: Session = Depends(get_db)):
    try:
        document = _get_document(db, public_uuid)
    except HTTPException as e:
        if e.status_code == 410:
            return HTMLResponse(EXPIRED_PAGE, status_code=410)
        raise

    if document.status == "draft":  # клиент открыл ссылку — смета «отправлена»
        document.status = "sent"
        db.commit()

    profile = db.get(Profile, document.user_id)
    og_image_url = str(request.url_for("public_og_image", public_uuid=public_uuid))
    return HTMLResponse(doc_service.render_public_page(document, profile, og_image_url))


@router.get("/{public_uuid}/og.png", name="public_og_image")
def public_og_image(public_uuid: str, db: Session = Depends(get_db)):
    """Картинка-превью для мессенджеров (og:image), кэш в хранилище."""
    document = _get_document(db, public_uuid)
    profile = db.get(Profile, document.user_id)
    png = og_card.get_or_render(document, profile)
    return Response(content=png, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=86400"})


@router.post("/{public_uuid}/approve")
def approve(public_uuid: str, db: Session = Depends(get_db)):
    document = _get_document(db, public_uuid)
    if document.status != "approved":
        document.status = "approved"
        db.commit()
    return RedirectResponse(url=f"/e/{public_uuid}", status_code=303)


@router.get("/{public_uuid}/pdf")
def public_pdf(public_uuid: str, db: Session = Depends(get_db)):
    document = _get_document(db, public_uuid)
    if not document.pdf_key:
        raise HTTPException(status_code=404, detail="PDF не найден")
    data, content_type = storage.get_object(document.pdf_key)
    return Response(
        content=data,
        media_type=content_type,
        headers={"Content-Disposition": f'inline; filename="smeta-{document.id}.pdf"'},
    )
