"""Админ-минимум (/admin, basic auth): пользователи, документы, конверсия Free→Pro.

Включается переменными ADMIN_USER / ADMIN_PASSWORD; если пароль пуст —
роут отвечает 404 (админки «нет»).
"""
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Document, Subscription, User
from app.services.billing import effective_plan

router = APIRouter(prefix="/admin", tags=["admin"])
_basic = HTTPBasic(auto_error=False)


def _require_admin(credentials: HTTPBasicCredentials | None = Depends(_basic)) -> None:
    if not settings.admin_password:
        raise HTTPException(status_code=404, detail="Not Found")
    ok = (
        credentials is not None
        and secrets.compare_digest(credentials.username, settings.admin_user)
        and secrets.compare_digest(credentials.password, settings.admin_password)
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется вход",
            headers={"WWW-Authenticate": "Basic"},
        )


PAGE = """<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex"><title>СметаПро — админ</title>
<style>
body{{font-family:system-ui,sans-serif;background:#f4f6fa;color:#17212b;margin:0;font-size:15px}}
.wrap{{max-width:860px;margin:0 auto;padding:20px 16px}}
h1{{font-size:22px}} h2{{font-size:17px;margin:22px 0 8px}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}}
.tile{{background:#fff;border-radius:12px;padding:14px}}
.tile b{{display:block;font-size:24px}} .tile span{{color:#6b7a8c;font-size:13px}}
table{{width:100%;border-collapse:collapse;background:#fff;border-radius:12px;overflow:hidden}}
th,td{{padding:8px 10px;border-bottom:1px solid #eef2f7;text-align:left;font-size:14px}}
th{{background:#eef3fb;color:#333}}
.pro{{color:#1b7f3b;font-weight:600}}
</style></head><body><div class="wrap">
<h1>СметаПро — метрики</h1>
<div class="tiles">
  <div class="tile"><b>{users_total}</b><span>пользователей всего</span></div>
  <div class="tile"><b>{users_7d}</b><span>регистраций за 7 дней</span></div>
  <div class="tile"><b>{users_30d}</b><span>за 30 дней</span></div>
  <div class="tile"><b>{docs_total}</b><span>документов всего</span></div>
  <div class="tile"><b>{docs_30d}</b><span>документов за 30 дней</span></div>
  <div class="tile"><b>{pro_users}</b><span>Pro-подписок</span></div>
  <div class="tile"><b>{conversion}%</b><span>конверсия Free→Pro</span></div>
  <div class="tile"><b>{estimates} / {contracts} / {acts}</b><span>смет / договоров / актов</span></div>
</div>
<h2>Последние пользователи</h2>
<table>
<tr><th>id</th><th>телефон</th><th>регистрация</th><th>тариф</th><th>документов</th></tr>
{user_rows}
</table>
</div></body></html>"""


@router.get("", response_class=HTMLResponse, dependencies=[Depends(_require_admin)])
def admin_page(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)

    def count(stmt) -> int:
        return db.scalar(stmt) or 0

    users_total = count(select(func.count()).select_from(User))
    users_7d = count(
        select(func.count()).select_from(User).where(User.created_at > now - timedelta(days=7))
    )
    users_30d = count(
        select(func.count()).select_from(User).where(User.created_at > now - timedelta(days=30))
    )
    docs_total = count(select(func.count()).select_from(Document))
    docs_30d = count(
        select(func.count())
        .select_from(Document)
        .where(Document.created_at > now - timedelta(days=30))
    )
    by_type = dict(
        db.execute(select(Document.type, func.count()).group_by(Document.type)).all()
    )
    pro_users = sum(
        1 for sub in db.scalars(select(Subscription)).all()
        if effective_plan(sub, now) == "pro"
    )
    conversion = round(pro_users / users_total * 100, 1) if users_total else 0.0

    doc_counts = dict(
        db.execute(select(Document.user_id, func.count()).group_by(Document.user_id)).all()
    )
    subs = {s.user_id: s for s in db.scalars(select(Subscription)).all()}
    rows = []
    for user in db.scalars(select(User).order_by(User.id.desc()).limit(20)).all():
        plan = effective_plan(subs.get(user.id), now)
        rows.append(
            f"<tr><td>{user.id}</td><td>{user.phone}</td>"
            f"<td>{user.created_at:%d.%m.%Y}</td>"
            f"<td class={'pro' if plan == 'pro' else 'free'}>{plan}</td>"
            f"<td>{doc_counts.get(user.id, 0)}</td></tr>"
        )

    return PAGE.format(
        users_total=users_total, users_7d=users_7d, users_30d=users_30d,
        docs_total=docs_total, docs_30d=docs_30d,
        estimates=by_type.get("estimate", 0), contracts=by_type.get("contract", 0),
        acts=by_type.get("act", 0),
        pro_users=pro_users, conversion=conversion,
        user_rows="".join(rows) or "<tr><td colspan=5>пока пусто</td></tr>",
    )
