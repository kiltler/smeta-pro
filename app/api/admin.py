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
:root{{--bg:#f5f5f2;--surface:#fff;--surface-2:#eef0f3;--text:#141a22;--text-2:#6d7684;
--border:rgba(20,26,34,.08);--accent:#2e5fe8;--success:#189a58;
--hero-a:#3565ec;--hero-b:#5b54e8;--hero-c:#3d7bea;
--shadow:0 1px 2px rgba(16,24,40,.05),0 4px 14px rgba(16,24,40,.06)}}
@media (prefers-color-scheme: dark){{:root{{--bg:#0e1420;--surface:#17202f;--surface-2:#202b3d;
--text:#eef2f8;--text-2:#94a0b3;--border:rgba(255,255,255,.08);--accent:#5f8bff;--success:#3ecf82;
--hero-a:#1b2a5e;--hero-b:#34246b;--hero-c:#143a72;--shadow:0 1px 0 rgba(255,255,255,.03) inset}}}}
*{{box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,Roboto,Inter,"Segoe UI",system-ui,sans-serif;
background:var(--bg);color:var(--text);margin:0;font-size:15px;line-height:1.45}}
.hero{{background:linear-gradient(115deg,var(--hero-a),var(--hero-b) 45%,var(--hero-c) 85%,var(--hero-a));
background-size:300% 300%;animation:drift 26s ease-in-out infinite alternate;
color:#fff;padding:26px 16px 30px;border-radius:0 0 22px 22px}}
@keyframes drift{{from{{background-position:0% 40%}}to{{background-position:100% 60%}}}}
.hero h1{{max-width:860px;margin:0 auto;font-size:22px;letter-spacing:-.01em}}
.wrap{{max-width:860px;margin:0 auto;padding:20px 16px 40px}}
h2{{font-size:17px;margin:26px 0 10px}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}}
.tile{{background:var(--surface);border:1px solid var(--border);border-radius:16px;
padding:16px;box-shadow:var(--shadow)}}
.tile b{{display:block;font-size:28px;font-weight:700;font-variant-numeric:tabular-nums;
letter-spacing:-.01em;line-height:1.2}}
.tile span{{color:var(--text-2);font-size:13px}}
.trend{{display:inline-block;margin-top:6px;font-size:12.5px;font-weight:600;color:var(--success)}}
table{{width:100%;border-collapse:collapse;background:var(--surface);border:1px solid var(--border);
border-radius:16px;overflow:hidden;box-shadow:var(--shadow)}}
th,td{{padding:10px 12px;text-align:left;font-size:14px}}
th{{background:var(--surface-2);color:var(--text-2);font-size:12.5px;
text-transform:uppercase;letter-spacing:.04em}}
tr:nth-child(even) td{{background:var(--surface-2)}}
td{{font-variant-numeric:tabular-nums}}
.pro{{color:var(--success);font-weight:700}} .free{{color:var(--text-2)}}
@media (prefers-reduced-motion: reduce){{*{{animation:none!important}}}}
</style></head><body>
<header class="hero"><h1>СметаПро — метрики</h1></header>
<div class="wrap">
<div class="tiles">
  <div class="tile"><b>{users_total}</b><span>пользователей всего</span>
    <div class="trend">↗ +{users_7d} за 7 дней · +{users_30d} за 30</div></div>
  <div class="tile"><b>{docs_total}</b><span>документов всего</span>
    <div class="trend">↗ +{docs_30d} за 30 дней</div></div>
  <div class="tile"><b>{pro_users}</b><span>Pro-подписок</span>
    <div class="trend">конверсия Free→Pro: {conversion}%</div></div>
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
