"""статус документа 'paid'

Revision ID: a1f2c3d4e5f6
Revises: be95c6506ee6
Create Date: 2026-07-09

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1f2c3d4e5f6"
down_revision: Union[str, None] = "be95c6506ee6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # имя без префикса: naming convention сама даёт ck_documents_status_valid
    op.drop_constraint("status_valid", "documents", type_="check")
    op.create_check_constraint(
        "status_valid", "documents", "status IN ('draft', 'sent', 'approved', 'paid')"
    )


def downgrade() -> None:
    # оплаченные откатываем в «согласована», иначе старый констрейнт не встанет
    op.execute("UPDATE documents SET status = 'approved' WHERE status = 'paid'")
    op.drop_constraint("status_valid", "documents", type_="check")
    op.create_check_constraint(
        "status_valid", "documents", "status IN ('draft', 'sent', 'approved')"
    )
