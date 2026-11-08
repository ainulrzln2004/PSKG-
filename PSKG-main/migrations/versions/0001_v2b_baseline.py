"""Baseline: Pilot V2B schema (previously created by Base.metadata.create_all).

For an existing V2B database (tables already present, no alembic_version table) every
create is skipped, so the existing data is kept untouched. For a new database the V2B
tables are created so that both paths continue through identical migrations.

Revision ID: 0001_v2b_baseline
Revises:
Create Date: 2026-10-24
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_v2b_baseline"
down_revision = None
branch_labels = None
depends_on = None


def _has(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _has("institutions"):
        op.create_table(
            "institutions",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("name", sa.String, nullable=False),
            sa.Column("code", sa.String, nullable=False),
            sa.Column("status", sa.String, nullable=False),
        )
        op.create_index("ix_institutions_name", "institutions", ["name"], unique=True)
        op.create_index("ix_institutions_code", "institutions", ["code"], unique=True)
    if not _has("kpis"):
        op.create_table(
            "kpis",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("teras", sa.Integer, nullable=False),
            sa.Column("title", sa.String, nullable=False),
            sa.Column("unit", sa.String, nullable=False),
            sa.Column("formula_status", sa.String, nullable=False),
        )
    if not _has("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("email", sa.String, nullable=False),
            sa.Column("name", sa.String, nullable=False),
            sa.Column("password_digest", sa.String, nullable=False),
            sa.Column("role", sa.String, nullable=False),
            sa.Column("institution_id", sa.Integer, sa.ForeignKey("institutions.id"), nullable=True),
            sa.Column("status", sa.String, nullable=False),
        )
        op.create_index("ix_users_email", "users", ["email"], unique=True)
    if not _has("targets"):
        op.create_table(
            "targets",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("kpi_id", sa.Integer, sa.ForeignKey("kpis.id"), nullable=False),
            sa.Column("year", sa.Integer, nullable=False),
            sa.Column("value", sa.Float, nullable=True),
            sa.UniqueConstraint("kpi_id", "year"),
        )
    if not _has("login_sessions"):
        op.create_table(
            "login_sessions",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
            sa.Column("token_digest", sa.String, nullable=False),
            sa.Column("expires_at", sa.DateTime, nullable=False),
        )
        op.create_index("ix_login_sessions_token_digest", "login_sessions", ["token_digest"], unique=True)
    if not _has("submissions"):
        op.create_table(
            "submissions",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("institution_id", sa.Integer, sa.ForeignKey("institutions.id"), nullable=False),
            sa.Column("kpi_id", sa.Integer, sa.ForeignKey("kpis.id"), nullable=False),
            sa.Column("year", sa.Integer, nullable=False),
            sa.Column("numerator", sa.Float, nullable=False),
            sa.Column("denominator", sa.Float, nullable=True),
            sa.Column("evidence_note", sa.String, nullable=False),
            sa.Column("status", sa.String, nullable=False),
            sa.Column("submitted_by", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
            sa.Column("reviewed_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
            sa.Column("review_note", sa.String, nullable=False),
            sa.Column("updated_at", sa.DateTime, nullable=False),
            sa.UniqueConstraint("institution_id", "kpi_id", "year"),
        )
    if not _has("audit_log"):
        op.create_table(
            "audit_log",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("actor_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
            sa.Column("event", sa.String, nullable=False),
            sa.Column("record", sa.String, nullable=False),
            sa.Column("at", sa.DateTime, nullable=False),
        )


def downgrade() -> None:
    raise RuntimeError("Downgrade of the baseline is not supported (would destroy data).")
