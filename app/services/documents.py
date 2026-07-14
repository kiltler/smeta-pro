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
from app.services import billing

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


_UNITS = ["", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"]
_UNITS_F = ["", "одна", "две", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"]
_TEENS = ["десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать",
          "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать"]
_TENS = ["", "", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят",
         "семьдесят", "восемьдесят", "девяносто"]
_HUNDREDS = ["", "сто", "двести", "триста", "четыреста", "пятьсот", "шестьсот",
             "семьсот", "восемьсот", "девятьсот"]


def _triple_words(n: int, feminine: bool) -> str:
    units = _UNITS_F if feminine else _UNITS
    words = [_HUNDREDS[n // 100]]
    rest = n % 100
    if 10 <= rest <= 19:
        words.append(_TEENS[rest - 10])
    else:
        words.append(_TENS[rest // 10])
        words.append(units[rest % 10])
    return " ".join(w for w in words if w)


def _plural(n: int, forms: tuple[str, str, str]) -> str:
    if 11 <= n % 100 <= 14:
        return forms[2]
    return {1: forms[0], 2: forms[1], 3: forms[1], 4: forms[1]}.get(n % 10, forms[2])


def rubles_in_words(value) -> str:
    """17700.50 → «семнадцать тысяч семьсот рублей 50 копеек» (до миллиардов)."""
    d = Decimal(str(value)).quantize(Decimal("0.01"))
    rubles, kopecks = int(d), int((d - int(d)) * 100)
    if rubles == 0:
        text = "ноль"
    else:
        parts = []
        for divisor, feminine, forms in [
            (10**9, False, ("миллиард", "миллиарда", "миллиардов")),
            (10**6, False, ("миллион", "миллиона", "миллионов")),
            (10**3, True, ("тысяча", "тысячи", "тысяч")),
        ]:
            group = rubles // divisor % 1000
            if group:
                parts.append(f"{_triple_words(group, feminine)} {_plural(group, forms)}")
        if rubles % 1000:
            parts.append(_triple_words(rubles % 1000, False))
        text = " ".join(parts)
    text += f" {_plural(rubles, ('рубль', 'рубля', 'рублей'))}"
    if kopecks:
        text += f" {kopecks:02d} {_plural(kopecks, ('копейка', 'копейки', 'копеек'))}"
    return text


def build_payload(
    positions: list[dict], client_name: str | None, watermark: bool = False
) -> dict:
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
    return {
        "client_name": client_name,
        "positions": snapshot,
        "total": str(total),
        # знак Free фиксируется в снапшоте: тариф на момент создания документа
        "watermark": watermark,
    }


WATERMARK_TEXT = "Создано в СметаПро — smeta-pro.ru"


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
        "watermark": document.payload.get("watermark", False),
        "watermark_text": WATERMARK_TEXT,
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
    watermark = not billing.user_is_pro(session, user)
    document = Document(
        user_id=user.id,
        type="estimate",
        status="draft",
        payload=build_payload(positions, client_name, watermark),
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


def _contract_context(
    contract: Document, act: Document, profile: Profile | None, user: User
) -> dict:
    payload = contract.payload
    return {
        "contract_number": contract.id,
        "contract_date": contract.created_at.strftime("%d.%m.%Y"),
        "act_number": act.id,
        "act_date": act.created_at.strftime("%d.%m.%Y"),
        "estimate_number": payload["estimate_number"],
        "estimate_date": payload["estimate_date"],
        "work_deadline": payload["work_deadline"],
        "client": payload["client"],
        "contractor": {
            "brand_name": (profile.brand_name if profile else None) or "Исполнитель",
            "full_name": profile.full_name if profile else None,
            "inn": profile.inn if profile else None,
            "requisites": (profile.requisites or {}).get("text", "") if profile else "",
            "phone": user.phone,
        },
        "positions": payload["positions"],
        "total": payload["total"],
        "total_words": rubles_in_words(payload["total"]),
        "watermark": payload.get("watermark", False),
        "watermark_text": WATERMARK_TEXT,
    }


def render_contract_html(
    contract: Document, act: Document, profile: Profile | None, user: User
) -> str:
    return _env.get_template("pdf/contract.html").render(
        _contract_context(contract, act, profile, user)
    )


def render_act_html(
    contract: Document, act: Document, profile: Profile | None, user: User
) -> str:
    return _env.get_template("pdf/act.html").render(
        _contract_context(contract, act, profile, user)
    )


def create_contract_and_act(
    session: Session, user: User, estimate: Document, client: dict, work_deadline: str
) -> tuple[Document, Document]:
    """Договор и акт из согласованной сметы: parent_id → смета, payload — снапшот."""
    now = datetime.now(timezone.utc)
    payload = {
        "client": client,
        "positions": estimate.payload["positions"],  # снапшот сметы, не прайса
        "total": estimate.payload["total"],
        "estimate_number": estimate.id,
        "estimate_date": estimate.created_at.strftime("%d.%m.%Y"),
        "work_deadline": work_deadline,
        "watermark": not billing.user_is_pro(session, user),
    }
    contract = Document(
        user_id=user.id, type="contract", status="draft",
        payload=payload, parent_id=estimate.id, created_at=now,
    )
    act = Document(
        user_id=user.id, type="act", status="draft",
        payload=payload, parent_id=estimate.id, created_at=now,
    )
    session.add_all([contract, act])
    session.flush()  # нужны id для номеров документов

    profile = session.get(Profile, user.id)
    for document, html in [
        (contract, render_contract_html(contract, act, profile, user)),
        (act, render_act_html(contract, act, profile, user)),
    ]:
        pdf_key = f"documents/{user.id}/{document.type}-{document.id}.pdf"
        storage.put_object(pdf_key, HTML(string=html).write_pdf(), "application/pdf")
        document.pdf_key = pdf_key

    session.commit()
    logger.info("Договор №%d и акт №%d к смете №%d", contract.id, act.id, estimate.id)
    return contract, act


def duplicate_estimate(session: Session, user: User, source: Document) -> Document:
    """Дубль сметы: тот же снапшот, новый номер/ссылка/срок/PDF."""
    return create_estimate(
        session,
        user,
        source.payload["positions"],
        source.payload.get("client_name"),
    )


def set_client_name(session: Session, document: Document, client_name: str) -> None:
    """Дописывает имя заказчика в смету. Позиции и суммы (снапшот) не трогаем,
    PDF перегенерируется на том же ключе — публичная ссылка не меняется."""
    document.payload = {**document.payload, "client_name": client_name}
    profile = session.get(Profile, document.user_id)
    pdf_bytes = HTML(string=render_estimate_html(document, profile)).write_pdf()
    storage.put_object(document.pdf_key, pdf_bytes, "application/pdf")
    session.commit()


def is_expired(document: Document) -> bool:
    return document.expires_at is not None and document.expires_at < datetime.now(timezone.utc)
