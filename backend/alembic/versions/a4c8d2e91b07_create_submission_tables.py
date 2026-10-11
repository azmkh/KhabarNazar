"""create_submission_tables

Revision ID: a4c8d2e91b07
Revises: 79aafe1355a3
Create Date: 2026-10-04 13:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a4c8d2e91b07"
down_revision: Union[str, None] = "79aafe1355a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "submissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("submission_type", sa.String(length=20), nullable=False),
        sa.Column("detected_language", sa.String(length=50), nullable=True),
        sa.Column("is_news", sa.Boolean(), nullable=False),
        sa.Column("news_confidence", sa.Float(), nullable=True),
        sa.Column("combined_risk_score", sa.Float(), nullable=True),
        sa.Column("final_label", sa.String(length=50), nullable=False),
        sa.Column("final_label_source", sa.String(length=50), nullable=False),
        sa.Column("admin_comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_submissions_id"), "submissions", ["id"], unique=False)
    op.create_index(op.f("ix_submissions_user_id"), "submissions", ["user_id"], unique=False)

    op.create_table(
        "text_submissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("submission_id", sa.Integer(), nullable=False),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("detected_language", sa.String(length=50), nullable=True),
        sa.Column("text_prediction", sa.String(length=50), nullable=True),
        sa.Column("text_confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("submission_id"),
    )
    op.create_index(op.f("ix_text_submissions_id"), "text_submissions", ["id"], unique=False)

    op.create_table(
        "image_submissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("submission_id", sa.Integer(), nullable=False),
        sa.Column("image_path", sa.String(length=512), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("ocr_text", sa.Text(), nullable=True),
        sa.Column("ocr_confidence", sa.Float(), nullable=True),
        sa.Column("detected_language", sa.String(length=50), nullable=True),
        sa.Column("image_score", sa.Float(), nullable=True),
        sa.Column("manipulation_prediction", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("submission_id"),
    )
    op.create_index(op.f("ix_image_submissions_id"), "image_submissions", ["id"], unique=False)

    op.create_table(
        "explainability",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("submission_id", sa.Integer(), nullable=False),
        sa.Column("highlighted_words", sa.Text(), nullable=True),
        sa.Column("heatmap_path", sa.String(length=512), nullable=True),
        sa.Column("explanation_summary", sa.Text(), nullable=True),
        sa.Column("model_version", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("submission_id"),
    )
    op.create_index(op.f("ix_explainability_id"), "explainability", ["id"], unique=False)

    op.create_table(
        "disputes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("submission_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("evidence_link", sa.String(length=512), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("admin_decision", sa.String(length=20), nullable=True),
        sa.Column("admin_comment", sa.Text(), nullable=True),
        sa.Column("override_label", sa.String(length=50), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_disputes_id"), "disputes", ["id"], unique=False)
    op.create_index(op.f("ix_disputes_submission_id"), "disputes", ["submission_id"], unique=False)
    op.create_index(op.f("ix_disputes_user_id"), "disputes", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_disputes_user_id"), table_name="disputes")
    op.drop_index(op.f("ix_disputes_submission_id"), table_name="disputes")
    op.drop_index(op.f("ix_disputes_id"), table_name="disputes")
    op.drop_table("disputes")
    op.drop_index(op.f("ix_explainability_id"), table_name="explainability")
    op.drop_table("explainability")
    op.drop_index(op.f("ix_image_submissions_id"), table_name="image_submissions")
    op.drop_table("image_submissions")
    op.drop_index(op.f("ix_text_submissions_id"), table_name="text_submissions")
    op.drop_table("text_submissions")
    op.drop_index(op.f("ix_submissions_user_id"), table_name="submissions")
    op.drop_index(op.f("ix_submissions_id"), table_name="submissions")
    op.drop_table("submissions")
