"""store timestamps with time zone; make is_news nullable

Revision ID: d2e7b4c19a35
Revises: c81f2a9b6714
Create Date: 2026-10-04 15:30:00.000000

- Timestamps were written as UTC but stored in "timestamp without time zone"
  columns, so PostgreSQL converted them to the server's local time zone.
  They are now "timestamp with time zone" (PostgreSQL only; SQLite has no
  time zone type and keeps storing UTC text).
- is_news defaulted to True although no news/non-news classifier exists.
  It is now nullable, and existing values (all from that default) are cleared.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d2e7b4c19a35"
down_revision: Union[str, None] = "c81f2a9b6714"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TIMESTAMP_COLUMNS = {
    "users": ["created_at", "updated_at"],
    "submissions": ["created_at"],
    "text_submissions": ["created_at"],
    "image_submissions": ["created_at"],
    "explainability": ["created_at"],
    "disputes": ["created_at", "reviewed_at"],
}


def upgrade() -> None:
    is_postgres = op.get_bind().dialect.name == "postgresql"

    if is_postgres:
        for table, columns in TIMESTAMP_COLUMNS.items():
            for column in columns:
                op.alter_column(
                    table,
                    column,
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    postgresql_using=f"{column} AT TIME ZONE current_setting('TimeZone')",
                )

    with op.batch_alter_table("submissions") as batch_op:
        batch_op.alter_column("is_news", existing_type=sa.Boolean(), nullable=True)
    op.execute("UPDATE submissions SET is_news = NULL")


def downgrade() -> None:
    is_postgres = op.get_bind().dialect.name == "postgresql"

    op.execute("UPDATE submissions SET is_news = TRUE WHERE is_news IS NULL")
    with op.batch_alter_table("submissions") as batch_op:
        batch_op.alter_column("is_news", existing_type=sa.Boolean(), nullable=False)

    if is_postgres:
        for table, columns in TIMESTAMP_COLUMNS.items():
            for column in columns:
                op.alter_column(
                    table,
                    column,
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    postgresql_using=f"{column} AT TIME ZONE current_setting('TimeZone')",
                )
