"""Документы: смета — снапшот в payload, PDF через WeasyPrint, публичная ссылка.

Правила (CLAUDE.md):
- payload — снапшот: изменение прайса задним числом не меняет документ;
- public_uuid неугадываемый, срок жизни ссылки = сроку сметы (14 дней);
- PDF лежит в хранилище (stateless), ключ — в pdf_key.
"""
import base64
import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from sqlalchemy.orm import Session
from weasyprint import HTML

from app import storage
from app.models import Document, Profile, User

logger = logging.getLogger(__name__)

ESTIMATE_TTL_DAYS = 14
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def _money(value) -> str:
    """11500.00 → «11 500», 1500.50 → «1 500,50» (русский формат)."""
    d = Decimal(str(value))
    sign, digits = ("−", -d) if d < 0 else ("", d)
    integral = int(digits)
    frac = (digits - integral).quantize(Decimal("0.01"))
    text = f"{integral:,}".replace(",", " ")
    if frac:
        text += f",{int(frac * 100):02d}"
    return sign + text


_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)
_env.filters["money"] = _money


def _num(value: float) -> float | int:
    return int(value) if float(value).is_integer() else float(value)


def build_payload(positions: list[dict], client_name: str | None) -> dict:
    """Снапшот позиций и сумм для payload документа."""
    snapshot = []
    total = Decimal("0")
    for p in positions:
        price = Decimal(str(p["price"]))
        qty = Decimal(str(p["qty"]))
        amount = (price * qty).quantize(Decimal("0.01"))
        total += amount
        snapshot.append(
            {
                "name": p["name"],
                "unit": p["unit"],
                "price": str(price),
                "qty": _num(float(qty)),
                "amount": str(amount),
            }
        )
    return {"client_name": client_name, "positions": snapshot, "total": str(total)}


def _template_context(document: Document, profile: Profile | None) -> dict:
    requisites_text = (profile.requisites or {}).get("text", "") if profile else ""
    contractor_lines = "\n".join(
        line
        for line in [
            profile.full_name if profile else None,
            f"ИНН {profile.inn}" if profile and profile.inn else None,
            requisites_text or None,
        ]
        if line
    )

    logo_data_uri = None
    if profile and profile.logo_key:
        try:
            data, content_type = storage.get_object(profile.logo_key)
            logo_data_uri = f"data:{content_type};base64,{base64.b64encode(data).decode()}"
        except Exception:
            logger.warning("Логотип %s не прочитан из хранилища", profile.logo_key)

    return {
        "number": document.id,
        "status": document.status,
        "public_uuid": document.public_uuid,
        "created_date": document.created_at.strftime("%d.%m.%Y"),
        "valid_until": document.expires_at.strftime("%d.%m.%Y"),
        "brand_name": (profile.brand_name if profile else None) or "СметаПро",
        "full_name": profile.full_name if profile else None,
        "contractor_lines": contractor_lines,
        "logo_data_uri": logo_data_uri,
        "client_name": document.payload.get("client_name"),
        "positions": document.payload["positions"],
        "total": document.payload["total"],
    }


def render_estimate_html(document: Document, profile: Profile | None) -> str:
    return _env.get_template("pdf/estimate.html").render(_template_context(document, profile))


def render_public_page(document: Document, profile: Profile | None) -> str:
    return _env.get_template("public/estimate_page.html").render(
        _template_context(document, profile)
    )


def create_estimate(
    session: Session, user: User, positions: list[dict], client_name: str | None = None
) -> Document:
    """Создаёт смету: снапшот, неугадываемая ссылка, PDF в хранилище."""
    now = datetime.now(timezone.utc)
    document = Document(
        user_id=user.id,
        type="estimate",
        status="draft",
        payload=build_payload(positions, client_name),
        public_uuid=uuid.uuid4(),
        expires_at=now + timedelta(days=ESTIMATE_TTL_DAYS),
        created_at=now,
    )
    session.add(document)
    session.flush()  # нужен id для номера сметы

    profile = session.get(Profile, user.id)
    pdf_bytes = HTML(string=render_estimate_html(document, profile)).write_pdf()
    pdf_key = f"documents/{user.id}/{document.public_uuid}.pdf"
    storage.put_object(pdf_key, pdf_bytes, "application/pdf")
    document.pdf_key = pdf_key

    session.commit()
    logger.info("Смета №%d создана: позиций %d", document.id, len(positions))
    return document


def duplicate_estimate(session: Session, user: User, source: Document) -> Document:
    """Дубль сметы: тот же снапшот, новый номер/ссылка/срок/PDF."""
    return create_estimate(
        session,
        user,
        source.payload["positions"],
        source.payload.get("client_name"),
    )


def is_expired(document: Document) -> bool:
    return document.expires_at is not None and document.expires_at < datetime.now(timezone.utc)
