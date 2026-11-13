"""add ocr_status to image_submissions

Revision ID: e5b1c7a3d920
Revises: d2e7b4c19a35
Create Date: 2026-11-14 12:00:00.000000

Every image now goes through OCR *and* the image detector with Grad-CAM. Without a stored
status, "OCR failed" and "OCR found no text" looked the same (both leave ocr_text empty), so
the result screen could not say which happened. The column is nullable: rows saved earlier
keep NULL, and nothing else changes.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5b1c7a3d920"
down_revision: Union[str, None] = "d2e7b4c19a35"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("image_submissions", sa.Column("ocr_status", sa.String(length=30), nullable=True))


def downgrade() -> None:
    op.drop_column("image_submissions", "ocr_status")
