"""add extracted text prediction fields to image submissions

Revision ID: c81f2a9b6714
Revises: a4c8d2e91b07
Create Date: 2026-10-04 14:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c81f2a9b6714"
down_revision: Union[str, None] = "a4c8d2e91b07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("image_submissions", sa.Column("text_prediction", sa.String(length=50), nullable=True))
    op.add_column("image_submissions", sa.Column("text_confidence", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("image_submissions", "text_confidence")
    op.drop_column("image_submissions", "text_prediction")
