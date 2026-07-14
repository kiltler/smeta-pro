"""OG-карточка публичной сметы (превью в мессенджерах), 1200×630.

Рендер Pillow: тёмный фирменный градиент, бренд мастера крупно, сумма tabular,
«Смета № N». Кэш — в файловом хранилище по ключу og/{uuid}.png: карточка
детерминирована содержимым сметы (номер, бренд, сумма), регенерация не нужна.
"""
import io
import logging

from PIL import Image, ImageDraw, ImageFont

from app import storage
from app.models import Document, Profile

logger = logging.getLogger(__name__)

W, H = 1200, 630
FONT_DIR = "/usr/share/fonts/truetype/dejavu"
# тёмный фирменный градиент (токены hero тёмной темы)
GRAD = [(0x1B, 0x2A, 0x5E), (0x34, 0x24, 0x6B), (0x14, 0x3A, 0x72)]


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(f"{FONT_DIR}/{name}", size)


def _lerp(a: tuple, b: tuple, t: float) -> tuple:
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _gradient() -> Image.Image:
    """Диагональный трёхстоповый градиент, как в хиро-зонах."""
    img = Image.new("RGB", (W, H))
    px = img.load()
    for y in range(H):
        for x in range(0, W, 4):  # шаг 4px — быстрее, разницы не видно
            t = (x / W + y / H) / 2
            color = _lerp(GRAD[0], GRAD[1], t * 2) if t < 0.5 else _lerp(GRAD[1], GRAD[2], t * 2 - 1)
            for dx in range(4):
                if x + dx < W:
                    px[x + dx, y] = color
    return img


def _fit_text(draw: ImageDraw.ImageDraw, text: str, max_width: int, size: int) -> ImageFont.FreeTypeFont:
    """Уменьшает кегль, пока строка не влезет в max_width."""
    while size > 24:
        font = _font(size)
        if draw.textlength(text, font=font) <= max_width:
            return font
        size -= 6
    return _font(size)


def render_og_card(brand: str, number: int, total_text: str, valid_until: str) -> bytes:
    img = _gradient()
    draw = ImageDraw.Draw(img)
    pad = 88

    # плейсхолдер-знак мастера: скруглённый квадрат с первой буквой бренда
    mark = Image.new("RGBA", (108, 108), (0, 0, 0, 0))
    ImageDraw.Draw(mark).rounded_rectangle((0, 0, 107, 107), radius=28, fill=(255, 255, 255, 46))
    img.paste(mark, (pad, pad), mark)
    letter_font = _font(56)
    letter = (brand[:1] or "С").upper()
    lw = draw.textlength(letter, font=letter_font)
    draw.text((pad + 54 - lw / 2, pad + 22), letter, font=letter_font, fill="#ffffff")

    # бренд мастера крупно
    brand_font = _fit_text(draw, brand, W - 2 * pad - 140, 64)
    draw.text((pad + 140, pad + 22), brand, font=brand_font, fill="#f2f5fb")

    # «Смета № N»
    draw.text((pad, 300), f"Смета № {number}", font=_font(40, bold=False), fill=(235, 240, 250, 200))

    # сумма — главная величина карточки
    sum_font = _fit_text(draw, total_text, W - 2 * pad, 128)
    draw.text((pad, 360), total_text, font=sum_font, fill="#ffffff")

    # срок действия
    draw.text((pad, H - pad - 30), f"действительна до {valid_until}",
              font=_font(30, bold=False), fill=(235, 240, 250, 170))

    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def get_or_render(document: Document, profile: Profile | None) -> bytes:
    """Карточка из кэша хранилища; если нет — рендер и запись."""
    key = f"og/{document.public_uuid}.png"
    try:
        data, _ = storage.get_object(key)
        return data
    except Exception:
        pass  # нет в кэше — рендерим

    from app.services.documents import _money  # локальный импорт: без цикла

    brand = (
        (profile.brand_name if profile else None)
        or (profile.full_name if profile else None)
        or "Исполнитель"
    )
    png = render_og_card(
        brand=brand,
        number=document.id,
        total_text=f"{_money(document.payload['total'])} ₽",
        valid_until=document.expires_at.strftime("%d.%m.%Y"),
    )
    try:
        storage.put_object(key, png, "image/png")
    except Exception:
        logger.warning("OG-карточка %s не записана в кэш", key)
    return png
