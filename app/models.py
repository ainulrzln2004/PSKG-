"""SQLAlchemy ORM models for PSKG Monitor 2030.

The schema is created and evolved ONLY through Alembic migrations in /migrations.
Tables that existed in Pilot V2B (institutions, users, login_sessions, kpis, targets,
submissions, audit_log) keep their names so existing data is preserved.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- roles & statuses
ROLE_IPT = "ipt"            # Penyelaras IPT
ROLE_KPT = "kpt"            # Penyelaras KPT
ROLE_ADMIN = "admin"        # Pentadbir KPT
ROLE_EXEC = "executive"     # Pengurusan Tertinggi
ROLES = {
    ROLE_IPT: "Penyelaras IPT",
    ROLE_KPT: "Penyelaras KPT",
    ROLE_ADMIN: "Pentadbir KPT",
    ROLE_EXEC: "Pengurusan Tertinggi",
}

USER_PENDING = "pending"     # self-registered, awaiting KPT approval
USER_INVITED = "invited"     # pre-registered by KPT, awaiting activation
USER_ACTIVE = "active"
USER_INACTIVE = "inactive"   # deactivated
USER_REJECTED = "rejected"

APP_PENDING = "PENDING_APPROVAL"
APP_APPROVED = "APPROVED"
APP_REJECTED = "REJECTED"

S_NOT_STARTED = "NOT_STARTED"   # virtual: no row exists
S_DRAFT = "DRAFT"
S_SUBMITTED = "SUBMITTED"
S_RETURNED = "RETURNED"
S_VERIFIED = "VERIFIED"
S_NOT_APPLICABLE = "NOT_APPLICABLE"  # virtual: KPI not applicable for this institution/year


class Institution(Base):
    __tablename__ = "institutions"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    code: Mapped[str] = mapped_column(String, unique=True, index=True)
    status: Mapped[str] = mapped_column(String, default="ACTIVE")  # PENDING/ACTIVE/INACTIVE/REJECTED
    category: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    official_email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_via: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=True)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String)
    password_digest: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    role: Mapped[str] = mapped_column(String, default=ROLE_IPT)
    institution_id: Mapped[Optional[int]] = mapped_column(ForeignKey("institutions.id"), nullable=True)
    status: Mapped[str] = mapped_column(String, default=USER_PENDING)
    position: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    official_email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    can_verify: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=True)
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class LoginSession(Base):
    __tablename__ = "login_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    token_digest: Mapped[str] = mapped_column(String, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(200), index=True)
    ip_address: Mapped[str] = mapped_column(String(64), index=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class RateEvent(Base):
    """Generic throttling ledger for public forms (registration, status check, reset)."""
    __tablename__ = "rate_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    bucket: Mapped[str] = mapped_column(String(60), index=True)
    key: Mapped[str] = mapped_column(String(200), index=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class RegistrationApplication(Base):
    __tablename__ = "registration_applications"
    id: Mapped[int] = mapped_column(primary_key=True)
    ref_no: Mapped[str] = mapped_column(String(30), unique=True)
    status: Mapped[str] = mapped_column(String(30), default=APP_PENDING, index=True)
    institution_id: Mapped[Optional[int]] = mapped_column(ForeignKey("institutions.id"), nullable=True)
    inst_name: Mapped[str] = mapped_column(String(200))
    inst_code: Mapped[str] = mapped_column(String(40), index=True)
    inst_category: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    inst_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    inst_state: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    inst_email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    coordinator_name: Mapped[str] = mapped_column(String(150))
    position: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    official_email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    account_email: Mapped[str] = mapped_column(String(200), index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    status_code_digest: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    decided_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(30), default="SELF_REGISTRATION")
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)


class AccountInvitation(Base):
    """Single-use, expiring tokens for KPT pre-registration activation and password reset."""
    __tablename__ = "account_invitations"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    institution_id: Mapped[Optional[int]] = mapped_column(ForeignKey("institutions.id"), nullable=True)
    purpose: Mapped[str] = mapped_column(String(20), default="ACTIVATION")  # ACTIVATION / PASSWORD_RESET
    token_digest: Mapped[str] = mapped_column(String(128), unique=True)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class AccountApproval(Base):
    """Immutable history of account decisions (Sejarah Kelulusan)."""
    __tablename__ = "account_approvals"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[Optional[int]] = mapped_column(ForeignKey("registration_applications.id"), nullable=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    institution_id: Mapped[Optional[int]] = mapped_column(ForeignKey("institutions.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(40))
    actor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    link: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class EmailOutbox(Base):
    __tablename__ = "email_outbox"
    id: Mapped[int] = mapped_column(primary_key=True)
    to_email: Mapped[str] = mapped_column(String(200), index=True)
    subject: Mapped[str] = mapped_column(String(250))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20))  # SENT / FAILED / DEV_PREVIEW
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    kind: Mapped[str] = mapped_column(String(40), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class Kpi(Base):
    __tablename__ = "kpis"
    id: Mapped[int] = mapped_column(primary_key=True)
    teras: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String)
    unit: Mapped[str] = mapped_column(String)  # percent / count / index
    formula_status: Mapped[str] = mapped_column(String, default="draft")
    code: Mapped[Optional[str]] = mapped_column(String(20), unique=True, nullable=True)
    os_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    os_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    indicator: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    definition: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    outcome_2030: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    measurement: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    numerator_label: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    denominator_label: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    data_owner: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    aggregation: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    subset_ratio: Mapped[bool] = mapped_column(Boolean, default=True)
    itemised: Mapped[bool] = mapped_column(Boolean, default=False)
    config_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_ref: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    confirmation_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class Target(Base):
    __tablename__ = "targets"
    id: Mapped[int] = mapped_column(primary_key=True)
    kpi_id: Mapped[int] = mapped_column(ForeignKey("kpis.id"))
    year: Mapped[int] = mapped_column(Integer)
    value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    kind: Mapped[str] = mapped_column(String(20), default="value")  # value / milestone
    label: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (UniqueConstraint("kpi_id", "year"),)


class InstitutionTarget(Base):
    """Optional institution-level allocation set by KPT. Never derived automatically."""
    __tablename__ = "institution_targets"
    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"))
    kpi_id: Mapped[int] = mapped_column(ForeignKey("kpis.id"))
    year: Mapped[int] = mapped_column(Integer)
    value: Mapped[float] = mapped_column(Float)
    set_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    set_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("institution_id", "kpi_id", "year"),)


class ReportingPeriod(Base):
    __tablename__ = "reporting_periods"
    id: Mapped[int] = mapped_column(primary_key=True)
    year: Mapped[int] = mapped_column(Integer, unique=True)
    status: Mapped[str] = mapped_column(String(20), default="PLANNED")  # PLANNED / OPEN / CLOSED
    opens_on: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    closes_on: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class Submission(Base):
    __tablename__ = "submissions"
    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"))
    kpi_id: Mapped[int] = mapped_column(ForeignKey("kpis.id"))
    year: Mapped[int] = mapped_column(Integer)
    numerator: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    denominator: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    evidence_note: Mapped[str] = mapped_column(String, default="")  # Catatan / justifikasi
    status: Mapped[str] = mapped_column(String, default=S_DRAFT)
    submitted_by: Mapped[int] = mapped_column(ForeignKey("users.id"))  # creator (V2B semantics)
    reviewed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    review_note: Mapped[str] = mapped_column(String, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    index_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    index_excellent: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    details_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    last_submitted_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (UniqueConstraint("institution_id", "kpi_id", "year"),
                      Index("ix_submissions_year_status", "year", "status"))


class SubmissionRevision(Base):
    """Snapshot written on every save, submit, review or re-open (full history)."""
    __tablename__ = "submission_revisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(30))
    status_after: Mapped[str] = mapped_column(String(20))
    snapshot_json: Mapped[str] = mapped_column(Text)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class VerificationRecord(Base):
    """KPT verification decisions (Sejarah Pengesahan)."""
    __tablename__ = "verification_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    decision: Mapped[str] = mapped_column(String(20))  # VERIFIED / RETURNED / REOPENED
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    value_at_decision: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class EvidenceFile(Base):
    __tablename__ = "evidence_files"
    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), index=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"))
    kpi_id: Mapped[int] = mapped_column(ForeignKey("kpis.id"))
    year: Mapped[int] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer)
    original_name: Mapped[str] = mapped_column(String(255))
    stored_name: Mapped[str] = mapped_column(String(100), unique=True)
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    locked: Mapped[bool] = mapped_column(Boolean, default=False)  # True once part of a submitted revision
    withdrawn_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    withdrawn_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)


class KpiMilestone(Base):
    """National milestone records (e.g. Employer Satisfaction Index development, 2026–2027)."""
    __tablename__ = "kpi_milestones"
    id: Mapped[int] = mapped_column(primary_key=True)
    kpi_id: Mapped[int] = mapped_column(ForeignKey("kpis.id"))
    year: Mapped[int] = mapped_column(Integer)
    progress_pct: Mapped[float] = mapped_column(Float)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("kpi_id", "year"),)


class Audit(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    event: Mapped[str] = mapped_column(String)
    record: Mapped[str] = mapped_column(String)
    at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class AppSetting(Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
