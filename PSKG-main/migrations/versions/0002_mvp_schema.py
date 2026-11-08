"""PSKG Monitor 2030 MVP: registration approval, pre-registration, KPI dictionary,
revisions, evidence, verification history, notifications, reporting periods, settings.

Non-destructive: existing V2B rows are kept and translated:
  * institution status pending/active/rejected  -> PENDING/ACTIVE/REJECTED
  * user role reviewer -> kpt (Penyelaras KPT), viewer -> executive
  * submission status draft/submitted/approved/returned -> DRAFT/SUBMITTED/VERIFIED/RETURNED
  * V2B pending IPT users become PENDING_APPROVAL registration applications
  * KPI rows are enriched with official codes/labels; the Employer Satisfaction Index
    targets are filled from slide 26 (milestones 2026–2027; 60/70/75%).

Revision ID: 0002_mvp_schema
Revises: 0001_v2b_baseline
Create Date: 2026-10-24
"""
import json
import secrets
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = "0002_mvp_schema"
down_revision = "0001_v2b_baseline"
branch_labels = None
depends_on = None

TZ = sa.DateTime(timezone=True)


def _now():
    return datetime.now(timezone.utc)


def _cols(table):
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    from app.kpi_catalogue import KPI_CATALOGUE, kpi_config
    from app.config import DEFAULT_PILOT_NOTICE

    bind = op.get_bind()

    # ------------------------------------------------------------ existing tables
    with op.batch_alter_table("institutions") as b:
        b.add_column(sa.Column("category", sa.String(20), nullable=True))
        b.add_column(sa.Column("address", sa.Text, nullable=True))
        b.add_column(sa.Column("state", sa.String(60), nullable=True))
        b.add_column(sa.Column("official_email", sa.String(200), nullable=True))
        b.add_column(sa.Column("created_via", sa.String(30), nullable=True))
        b.add_column(sa.Column("is_demo", sa.Boolean, nullable=False, server_default=sa.false()))
        b.add_column(sa.Column("created_at", TZ, nullable=True))
    bind.execute(sa.text("UPDATE institutions SET status = UPPER(status), created_via = COALESCE(created_via, 'LEGACY_V2B')"))

    with op.batch_alter_table("users") as b:
        b.alter_column("password_digest", existing_type=sa.String, nullable=True)
        b.add_column(sa.Column("position", sa.String(150), nullable=True))
        b.add_column(sa.Column("department", sa.String(150), nullable=True))
        b.add_column(sa.Column("phone", sa.String(40), nullable=True))
        b.add_column(sa.Column("official_email", sa.String(200), nullable=True))
        b.add_column(sa.Column("can_verify", sa.Boolean, nullable=False, server_default=sa.true()))
        b.add_column(sa.Column("created_at", TZ, nullable=True))
        b.add_column(sa.Column("activated_at", TZ, nullable=True))
        b.add_column(sa.Column("last_login_at", TZ, nullable=True))
        b.add_column(sa.Column("password_changed_at", TZ, nullable=True))
    bind.execute(sa.text("UPDATE users SET role='kpt' WHERE role='reviewer'"))
    bind.execute(sa.text("UPDATE users SET role='executive' WHERE role='viewer'"))

    with op.batch_alter_table("login_sessions") as b:
        b.add_column(sa.Column("created_at", TZ, nullable=True))
        b.add_column(sa.Column("ip_address", sa.String(64), nullable=True))
        b.add_column(sa.Column("user_agent", sa.String(300), nullable=True))

    with op.batch_alter_table("kpis") as b:
        b.add_column(sa.Column("code", sa.String(20), nullable=True))
        b.add_column(sa.Column("os_code", sa.String(10), nullable=True))
        b.add_column(sa.Column("os_name", sa.String(120), nullable=True))
        b.add_column(sa.Column("indicator", sa.Text, nullable=True))
        b.add_column(sa.Column("definition", sa.Text, nullable=True))
        b.add_column(sa.Column("outcome_2030", sa.Text, nullable=True))
        b.add_column(sa.Column("measurement", sa.Text, nullable=True))
        b.add_column(sa.Column("numerator_label", sa.Text, nullable=True))
        b.add_column(sa.Column("denominator_label", sa.Text, nullable=True))
        b.add_column(sa.Column("data_owner", sa.Text, nullable=True))
        b.add_column(sa.Column("aggregation", sa.String(30), nullable=True))
        b.add_column(sa.Column("subset_ratio", sa.Boolean, nullable=False, server_default=sa.true()))
        b.add_column(sa.Column("itemised", sa.Boolean, nullable=False, server_default=sa.false()))
        b.add_column(sa.Column("config_json", sa.Text, nullable=True))
        b.add_column(sa.Column("source_ref", sa.String(120), nullable=True))
        b.add_column(sa.Column("confirmation_notes", sa.Text, nullable=True))
        b.add_column(sa.Column("sort_order", sa.Integer, nullable=True))
        b.create_unique_constraint("uq_kpis_code", ["code"])

    with op.batch_alter_table("targets") as b:
        b.add_column(sa.Column("kind", sa.String(20), nullable=False, server_default="value"))
        b.add_column(sa.Column("label", sa.String(120), nullable=True))
        b.add_column(sa.Column("updated_by", sa.Integer, nullable=True))
        b.add_column(sa.Column("updated_at", TZ, nullable=True))
        b.create_foreign_key("fk_targets_updated_by", "users", ["updated_by"], ["id"])

    with op.batch_alter_table("submissions") as b:
        b.alter_column("numerator", existing_type=sa.Float, nullable=True)
        b.add_column(sa.Column("value", sa.Float, nullable=True))
        b.add_column(sa.Column("index_score", sa.Float, nullable=True))
        b.add_column(sa.Column("index_excellent", sa.Boolean, nullable=True))
        b.add_column(sa.Column("details_json", sa.Text, nullable=True))
        b.add_column(sa.Column("revision", sa.Integer, nullable=False, server_default="0"))
        b.add_column(sa.Column("created_at", TZ, nullable=True))
        b.add_column(sa.Column("updated_by", sa.Integer, nullable=True))
        b.add_column(sa.Column("last_submitted_by", sa.Integer, nullable=True))
        b.add_column(sa.Column("submitted_at", TZ, nullable=True))
        b.add_column(sa.Column("reviewed_at", TZ, nullable=True))
        b.create_foreign_key("fk_submissions_updated_by", "users", ["updated_by"], ["id"])
        b.create_foreign_key("fk_submissions_last_submitted_by", "users", ["last_submitted_by"], ["id"])
        b.create_index("ix_submissions_year_status", ["year", "status"])
    for old, new in (("draft", "DRAFT"), ("submitted", "SUBMITTED"), ("approved", "VERIFIED"), ("returned", "RETURNED")):
        bind.execute(sa.text("UPDATE submissions SET status=:n WHERE status=:o"), {"n": new, "o": old})
    bind.execute(sa.text("UPDATE submissions SET created_at = updated_at WHERE created_at IS NULL"))

    with op.batch_alter_table("audit_log") as b:
        b.alter_column("actor_id", existing_type=sa.Integer, nullable=True)
        b.add_column(sa.Column("ip_address", sa.String(64), nullable=True))
        b.add_column(sa.Column("detail", sa.Text, nullable=True))

    # ------------------------------------------------------------ new tables
    op.create_table(
        "login_attempts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(200), nullable=False, index=True),
        sa.Column("ip_address", sa.String(64), nullable=False, index=True),
        sa.Column("success", sa.Boolean, nullable=False),
        sa.Column("at", TZ, nullable=False, index=True),
    )
    op.create_table(
        "rate_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("bucket", sa.String(60), nullable=False, index=True),
        sa.Column("key", sa.String(200), nullable=False, index=True),
        sa.Column("at", TZ, nullable=False, index=True),
    )
    op.create_table(
        "registration_applications",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ref_no", sa.String(30), nullable=False, unique=True),
        sa.Column("status", sa.String(30), nullable=False, index=True),
        sa.Column("institution_id", sa.Integer, sa.ForeignKey("institutions.id"), nullable=True),
        sa.Column("inst_name", sa.String(200), nullable=False),
        sa.Column("inst_code", sa.String(40), nullable=False, index=True),
        sa.Column("inst_category", sa.String(20), nullable=True),
        sa.Column("inst_address", sa.Text, nullable=True),
        sa.Column("inst_state", sa.String(60), nullable=True),
        sa.Column("inst_email", sa.String(200), nullable=True),
        sa.Column("coordinator_name", sa.String(150), nullable=False),
        sa.Column("position", sa.String(150), nullable=True),
        sa.Column("department", sa.String(150), nullable=True),
        sa.Column("official_email", sa.String(200), nullable=True),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("account_email", sa.String(200), nullable=False, index=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status_code_digest", sa.String(128), nullable=True),
        sa.Column("submitted_at", TZ, nullable=False),
        sa.Column("decided_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("decided_at", TZ, nullable=True),
        sa.Column("decision_reason", sa.Text, nullable=True),
        sa.Column("source", sa.String(30), nullable=False, server_default="SELF_REGISTRATION"),
        sa.Column("ip_address", sa.String(64), nullable=True),
    )
    op.create_table(
        "account_invitations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("institution_id", sa.Integer, sa.ForeignKey("institutions.id"), nullable=True),
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("token_digest", sa.String(128), nullable=False, unique=True),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("expires_at", TZ, nullable=False),
        sa.Column("used_at", TZ, nullable=True),
        sa.Column("revoked_at", TZ, nullable=True),
    )
    op.create_table(
        "account_approvals",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("application_id", sa.Integer, sa.ForeignKey("registration_applications.id"), nullable=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("institution_id", sa.Integer, sa.ForeignKey("institutions.id"), nullable=True),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("actor_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("at", TZ, nullable=False, index=True),
    )
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("link", sa.String(300), nullable=True),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("read_at", TZ, nullable=True),
    )
    op.create_table(
        "email_outbox",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("to_email", sa.String(200), nullable=False, index=True),
        sa.Column("subject", sa.String(250), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("sent_at", TZ, nullable=True),
    )
    op.create_table(
        "institution_targets",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("institution_id", sa.Integer, sa.ForeignKey("institutions.id"), nullable=False),
        sa.Column("kpi_id", sa.Integer, sa.ForeignKey("kpis.id"), nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("value", sa.Float, nullable=False),
        sa.Column("set_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("set_at", TZ, nullable=False),
        sa.UniqueConstraint("institution_id", "kpi_id", "year"),
    )
    op.create_table(
        "reporting_periods",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("year", sa.Integer, nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("opens_on", sa.String(10), nullable=True),
        sa.Column("closes_on", sa.String(10), nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("updated_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", TZ, nullable=True),
    )
    op.create_table(
        "submission_revisions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("submission_id", sa.Integer, sa.ForeignKey("submissions.id"), nullable=False, index=True),
        sa.Column("revision", sa.Integer, nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("status_after", sa.String(20), nullable=False),
        sa.Column("snapshot_json", sa.Text, nullable=False),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("actor_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("at", TZ, nullable=False),
    )
    op.create_table(
        "verification_history",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("submission_id", sa.Integer, sa.ForeignKey("submissions.id"), nullable=False, index=True),
        sa.Column("revision", sa.Integer, nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("reviewer_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("at", TZ, nullable=False),
        sa.Column("value_at_decision", sa.Float, nullable=True),
    )
    op.create_table(
        "evidence_files",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("submission_id", sa.Integer, sa.ForeignKey("submissions.id"), nullable=False, index=True),
        sa.Column("institution_id", sa.Integer, sa.ForeignKey("institutions.id"), nullable=False),
        sa.Column("kpi_id", sa.Integer, sa.ForeignKey("kpis.id"), nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("revision", sa.Integer, nullable=False),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("stored_name", sa.String(100), nullable=False, unique=True),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("uploaded_by", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("uploaded_at", TZ, nullable=False),
        sa.Column("locked", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("withdrawn_at", TZ, nullable=True),
        sa.Column("withdrawn_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_table(
        "kpi_milestones",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("kpi_id", sa.Integer, sa.ForeignKey("kpis.id"), nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("progress_pct", sa.Float, nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("recorded_by", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("recorded_at", TZ, nullable=False),
        sa.UniqueConstraint("kpi_id", "year"),
    )
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(80), primary_key=True),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("updated_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", TZ, nullable=True),
    )

    # ------------------------------------------------------------ reference data
    now = _now()
    kpis_t = sa.table("kpis", sa.column("id", sa.Integer), sa.column("teras", sa.Integer), sa.column("title", sa.String),
                      sa.column("unit", sa.String), sa.column("formula_status", sa.String))
    targets_t = sa.table("targets", sa.column("kpi_id", sa.Integer), sa.column("year", sa.Integer),
                         sa.column("value", sa.Float), sa.column("kind", sa.String), sa.column("label", sa.String))
    existing_ids = {r[0] for r in bind.execute(sa.text("SELECT id FROM kpis"))}
    for k in KPI_CATALOGUE:
        if k["id"] not in existing_ids:
            bind.execute(kpis_t.insert().values(id=k["id"], teras=k["teras"], title=k["title"], unit=k["unit"], formula_status="draft"))
        bind.execute(sa.text(
            "UPDATE kpis SET code=:code, teras=:teras, title=:title, unit=:unit, os_code=:os_code, os_name=:os_name, "
            "indicator=:indicator, definition=:definition, outcome_2030=:outcome, measurement=:measurement, "
            "numerator_label=:num, denominator_label=:den, data_owner=:owner, aggregation=:agg, subset_ratio=:subset, "
            "itemised=:itemised, config_json=:cfg, source_ref=:src, confirmation_notes=:notes, sort_order=:sort, "
            "formula_status='draft' WHERE id=:id"),
            dict(id=k["id"], code=k["code"], teras=k["teras"], title=k["title"], unit=k["unit"], os_code=k["os_code"],
                 os_name=k["os_name"], indicator=k["indicator"], definition=k["definition"], outcome=k["outcome_2030"],
                 measurement=k["measurement"], num=k["numerator_label"], den=k["denominator_label"], owner=k["data_owner"],
                 agg=k["aggregation"], subset=bool(k["subset_ratio"]), itemised=bool(k["itemised"]),
                 cfg=json.dumps(kpi_config(k), ensure_ascii=False), src=k["source_ref"],
                 notes=json.dumps(k["confirmation_notes"], ensure_ascii=False), sort=k["id"]))
        existing_t = {r[0]: r[1] for r in bind.execute(sa.text("SELECT year, value FROM targets WHERE kpi_id=:k"), {"k": k["id"]})}
        for year, t in zip(range(2026, 2031), k["targets"]):
            if year not in existing_t:
                bind.execute(targets_t.insert().values(kpi_id=k["id"], year=year, value=t["value"], kind=t["kind"], label=t["label"]))
            else:
                # V2B stored null for the slide-26 milestone/ambiguous cells; fill from the verified reading.
                if existing_t[year] is None or k["id"] == 17:
                    bind.execute(sa.text("UPDATE targets SET value=:v, kind=:kind, label=:label WHERE kpi_id=:k AND year=:y"),
                                 dict(v=t["value"], kind=t["kind"], label=t["label"], k=k["id"], y=year))

    # recompute stored achievement values for existing submissions
    for sid, unit, num, den in bind.execute(sa.text(
            "SELECT s.id, k.unit, s.numerator, s.denominator FROM submissions s JOIN kpis k ON k.id=s.kpi_id")).fetchall():
        value = None
        if unit == "percent" and num is not None and den:
            value = round(100.0 * num / den, 4)
        elif unit == "count" and num is not None:
            value = num
        bind.execute(sa.text("UPDATE submissions SET value=:v WHERE id=:id"), {"v": value, "id": sid})

    periods = sa.table("reporting_periods", sa.column("year", sa.Integer), sa.column("status", sa.String),
                       sa.column("note", sa.Text), sa.column("updated_at", TZ))
    for y in range(2026, 2031):
        bind.execute(periods.insert().values(year=y, status="OPEN" if y == 2026 else "PLANNED", note=None, updated_at=now))

    settings_t = sa.table("app_settings", sa.column("key", sa.String), sa.column("value", sa.Text), sa.column("updated_at", TZ))
    for key, val in (("pilot_notice_enabled", "true"), ("pilot_notice", DEFAULT_PILOT_NOTICE),
                     ("evidence_required_on_submit", "true"), ("default_reporting_year", "2026")):
        bind.execute(settings_t.insert().values(key=key, value=val, updated_at=now))

    # V2B pending IPT users -> registration applications awaiting Penyelaras KPT decision
    apps = sa.table("registration_applications", *[sa.column(c) for c in (
        "ref_no", "status", "institution_id", "inst_name", "inst_code", "coordinator_name", "account_email",
        "user_id", "submitted_at", "source")])
    rows = bind.execute(sa.text(
        "SELECT u.id, u.email, u.name, u.institution_id, i.name, i.code, i.status FROM users u "
        "LEFT JOIN institutions i ON i.id=u.institution_id WHERE u.role='ipt' AND u.status='pending'")).fetchall()
    for uid, email, name, inst_id, inst_name, inst_code, _ in rows:
        bind.execute(apps.insert().values(
            ref_no=f"REG-{now.year}-{secrets.token_hex(3).upper()}", status="PENDING_APPROVAL", institution_id=inst_id,
            inst_name=inst_name or "(tidak dinyatakan)", inst_code=inst_code or "-", coordinator_name=name,
            account_email=email, user_id=uid, submitted_at=now, source="LEGACY_V2B"))


def downgrade() -> None:
    raise RuntimeError("Downgrade not supported: restore from backup instead.")
