"""ИИ-парсер диктовок: текст → позиции сметы, сматченные с прайсом пользователя.

Схема работы:
1. Собираем каталог пользователя (позиции + комплекты) в текст.
2. Anthropic API возвращает строгий JSON: названия из каталога + количества
   (гарантия формата — output_config.format с JSON-схемой).
3. Сервер сопоставляет названия с id, раскрывает комплекты в позиции,
   подставляет цены. Несматченное честно уходит в unrecognized.
4. Каждый вызов пишется в parse_logs; правка пользователя — туда же
   (материал для улучшения промпта).
"""
import json
import logging
import re
from decimal import Decimal
from pathlib import Path

import anthropic
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Bundle, ParseLog, PriceItem, User

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
FEW_SHOT_COUNT = 4  # сколько диктовок из датасета уходит в промпт примерами

# Схема ответа модели: названия строго из каталога + количества
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "qty": {"type": "number"}},
                "required": ["name", "qty"],
                "additionalProperties": False,
            },
        },
        "bundles": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "qty": {"type": "number"}},
                "required": ["name", "qty"],
                "additionalProperties": False,
            },
        },
        "unrecognized": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["items", "bundles", "unrecognized"],
    "additionalProperties": False,
}


class ParserNotConfigured(Exception):
    """Не задан ANTHROPIC_API_KEY."""


def load_dataset() -> list[dict]:
    """Диктовки из app/prompts/dataset.md: [{"text": ..., "expected": {...}}, ...]."""
    raw = (PROMPTS_DIR / "dataset.md").read_text(encoding="utf-8")
    cases = []
    for block in re.split(r"^## ", raw, flags=re.M)[1:]:
        text_match = re.search(r"^Текст:\s*(.+)$", block, flags=re.M)
        json_match = re.search(r"```json\n(.*?)```", block, flags=re.S)
        if text_match and json_match:
            cases.append(
                {"text": text_match.group(1).strip(), "expected": json.loads(json_match.group(1))}
            )
    return cases


def build_system_prompt() -> str:
    template = (PROMPTS_DIR / "parser.md").read_text(encoding="utf-8")
    examples = []
    for case in load_dataset()[:FEW_SHOT_COUNT]:
        examples.append(
            f"Диктовка: «{case['text']}»\nОтвет: {json.dumps(case['expected'], ensure_ascii=False)}"
        )
    return template.replace("{{EXAMPLES}}", "\n\n".join(examples))


def _build_catalog(items: list[PriceItem], bundles: list[Bundle]) -> str:
    lines = ["Каталог позиций (название | синонимы | единица):"]
    for item in items:
        synonyms = ", ".join(item.synonyms or []) or "—"
        lines.append(f"- {item.name} | {synonyms} | {item.unit}")
    lines.append("\nКомплекты:")
    if bundles:
        lines.extend(f"- {b.name}" for b in bundles)
    else:
        lines.append("- (нет)")
    return "\n".join(lines)


def _call_model(system_prompt: str, user_message: str) -> dict:
    """Вызов Anthropic API. Вынесено отдельно, чтобы тесты подменяли одну функцию."""
    if not settings.anthropic_api_key:
        raise ParserNotConfigured
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=2000,
        thinking={"type": "disabled"},  # парсеру важна скорость, не рассуждения
        system=[
            {
                "type": "text",
                "text": system_prompt,
                # промпт одинаковый для всех пользователей — кэшируется
                "cache_control": {"type": "ephemeral"},
            }
        ],
        output_config={"format": {"type": "json_schema", "schema": RESPONSE_SCHEMA}},
        messages=[{"role": "user", "content": user_message}],
    )
    text = next(block.text for block in response.content if block.type == "text")
    return json.loads(text)


def _num(value: float) -> float | int:
    """1.0 → 1 (для аккуратного JSON), 1.5 остаётся 1.5."""
    return int(value) if float(value).is_integer() else float(value)


def parse_text(session: Session, user: User, text: str) -> dict:
    """Разбирает диктовку и возвращает позиции с ценами + id записи в parse_logs."""
    items = session.scalars(select(PriceItem).where(PriceItem.user_id == user.id)).all()
    bundles = session.scalars(select(Bundle).where(Bundle.user_id == user.id)).all()

    user_message = f"{_build_catalog(items, bundles)}\n\nДиктовка: «{text.strip()}»"
    raw = _call_model(build_system_prompt(), user_message)

    items_by_name = {i.name.casefold(): i for i in items}
    bundles_by_name = {b.name.casefold(): b for b in bundles}
    items_by_id = {i.id: i for i in items}

    positions: dict[int, dict] = {}  # price_item_id → позиция (дубли суммируются)
    unrecognized: list[str] = list(raw.get("unrecognized", []))

    def add_position(item: PriceItem, qty: float) -> None:
        pos = positions.setdefault(
            item.id,
            {
                "price_item_id": item.id,
                "name": item.name,
                "unit": item.unit,
                "price": str(item.price),
                "qty": 0,
            },
        )
        pos["qty"] = _num(pos["qty"] + qty)

    for entry in raw.get("items", []):
        item = items_by_name.get(entry["name"].strip().casefold())
        if item is None or entry["qty"] <= 0:
            unrecognized.append(entry["name"])
            continue
        add_position(item, entry["qty"])

    for entry in raw.get("bundles", []):
        bundle = bundles_by_name.get(entry["name"].strip().casefold())
        if bundle is None or entry["qty"] <= 0:
            unrecognized.append(entry["name"])
            continue
        for part in bundle.items:
            item = items_by_id.get(part["price_item_id"])
            if item is not None:
                add_position(item, part["qty_default"] * entry["qty"])

    result = {"positions": list(positions.values()), "unrecognized": unrecognized}

    log = ParseLog(user_id=user.id, raw_input=text, parsed_json=result)
    session.add(log)
    session.commit()

    total = sum(Decimal(p["price"]) * Decimal(str(p["qty"])) for p in result["positions"])
    logger.info(
        "Парсинг: позиций %d, нераспознанных %d, сумма %s",
        len(result["positions"]), len(unrecognized), total,
    )
    return {"parse_log_id": log.id, **result}


def save_correction(session: Session, user: User, log_id: int, corrected: dict) -> ParseLog | None:
    """Фиксирует правку пользователя после экрана проверки."""
    log = session.get(ParseLog, log_id)
    if log is None or log.user_id != user.id:
        return None
    log.corrected_json = corrected
    session.commit()
    return log
