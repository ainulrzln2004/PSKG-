"""Pentadbir KPT: users & roles, institutions, reporting periods, KPI targets, milestones,
audit log and system settings. Also: in-app notifications for every user."""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..config import INSTITUTION_CATEGORIES, STATES, YEARS, settings
from ..db import get_db
from ..models import (ROLE_ADMIN, ROLE_EXEC, ROLE_IPT, ROLE_KPT, ROLES, USER_ACTIVE, USER_INACTIVE, USER_INVITED,
                      AccountApproval, Audit, Institution, InstitutionTarget, Kpi, KpiMilestone, Notification,
                      ReportingPeriod, Submission, Target, User, utcnow)
from ..security import aware, current_user, normalise_email, require, revoke_user_sessions
from ..services import SETTING_DEFAULTS, audit, get_setting, set_setting
from .accounts import _dev_link, _issue_invitation
from .public import _clean, _phone

router = APIRouter(prefix="/api")


def _iso(dt):
    return aware(dt).isoformat() if dt else None


# ------------------------------------------------------------------ notifications (all users)
@router.get("/notifications")
def my_notifications(u: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Notification).where(Notification.user_id == u.id)
                      .order_by(Notification.created_at.desc()).limit(100))
    items = [{"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "link": n.link,
              "created_at": _iso(n.created_at), "read": n.read_at is not None} for n in rows]
    return {"unread": sum(1 for i in items if not i["read"]), "items": items}


@router.post("/notifications/read")
def mark_read(u: User = Depends(current_user), db: Session = Depends(get_db)):
    for n in db.scalars(select(Notification).where(Notification.user_id == u.id, Notification.read_at.is_(None))):
        n.read_at = utcnow()
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ users & roles
@router.get("/admin/users")
def list_users(q: str = "", role: str = "", u: User = Depends(require("admin.users")), db: Session = Depends(get_db)):
    query = select(User)
    if role:
        query = query.where(User.role == role)
    if q.strip():
        like = f"%{q.strip().lower()}%"
        query = query.where(or_(func.lower(User.name).like(like), func.lower(User.email).like(like)))
    out = []
    for x in db.scalars(query.order_by(User.role, User.name)):
        inst = db.get(Institution, x.institution_id) if x.institution_id else None
        out.append({"id": x.id, "name": x.name, "email": x.email, "role": x.role, "role_label": ROLES.get(x.role, x.role),
                    "status": x.status, "can_verify": x.can_verify, "institution": inst.name if inst else None,
                    "last_login_at": _iso(x.last_login_at)})
    return out


class StaffIn(BaseModel):
    name: str = Field(max_length=150)
    email: str = Field(max_length=200)
    role: str
    position: str = Field(default="", max_length=150)
    department: str = Field(default="", max_length=150)
    phone: str = Field(default="", max_length=40)
    can_verify: bool = True


@router.post("/admin/users", status_code=201)
def create_staff(req: StaffIn, request: Request, u: User = Depends(require("admin.users")), db: Session = Depends(get_db)):
    if req.role not in (ROLE_KPT, ROLE_ADMIN, ROLE_EXEC):
        raise HTTPException(422, "Peranan mesti Penyelaras KPT, Pentadbir KPT atau Pengurusan Tertinggi. "
                                 "Akaun IPT dicipta melalui Pra-Daftar Akaun IPT.")
    email = normalise_email(req.email)
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(409, "Emel telah digunakan.")
    name = _clean(req.name, 150)
    if len(name) < 3:
        raise HTTPException(422, "Nama wajib diisi.")
    x = User(email=email, name=name, role=req.role, status=USER_INVITED, password_digest=None,
             position=_clean(req.position, 150) or None, department=_clean(req.department, 150) or None,
             phone=_phone(req.phone) if req.phone.strip() else None, can_verify=req.can_verify)
    db.add(x)
    db.flush()
    token, inv = _issue_invitation(db, x, u)
    db.add(AccountApproval(user_id=x.id, action="STAFF_INVITED", actor_id=u.id, reason=ROLES[req.role]))
    audit(db, u, "staff_invited", f"user:{x.id}", request, role=req.role)
    db.commit()
    return {"user_id": x.id, "message": "Jemputan pengaktifan dihantar.", "dev_activation_link": _dev_link(token)}


class UserUpdateIn(BaseModel):
    role: Optional[str] = None
    status: Optional[str] = None
    can_verify: Optional[bool] = None
    reason: str = Field(default="", max_length=500)


def _active_admins(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(User).where(User.role == ROLE_ADMIN, User.status == USER_ACTIVE)) or 0


@router.patch("/admin/users/{uid}")
def update_user(uid: int, req: UserUpdateIn, request: Request, u: User = Depends(require("admin.users")),
                db: Session = Depends(get_db)):
    x = db.get(User, uid)
    if not x:
        raise HTTPException(404, "Pengguna tidak ditemui.")
    reason = _clean(req.reason, 500)
    if len(reason) < 5:
        raise HTTPException(422, "Nyatakan sebab perubahan.")
    changes = {}
    if req.role is not None and req.role != x.role:
        if req.role not in ROLES:
            raise HTTPException(422, "Peranan tidak sah.")
        if (x.role == ROLE_IPT) != (req.role == ROLE_IPT):
            raise HTTPException(422, "Akaun IPT dan akaun KPT diurus secara berasingan; peranan tidak boleh ditukar merentas.")
        if x.role == ROLE_ADMIN and _active_admins(db) <= 1:
            raise HTTPException(409, "Sekurang-kurangnya seorang Pentadbir KPT aktif diperlukan.")
        changes["role"] = (x.role, req.role)
        x.role = req.role
    if req.status is not None and req.status != x.status:
        if req.status not in (USER_ACTIVE, USER_INACTIVE):
            raise HTTPException(422, "Status mesti active atau inactive.")
        if x.id == u.id:
            raise HTTPException(409, "Anda tidak boleh menukar status akaun sendiri.")
        if req.status == USER_ACTIVE and not x.password_digest:
            raise HTTPException(409, "Akaun belum diaktifkan oleh pemiliknya.")
        if x.role == ROLE_ADMIN and req.status == USER_INACTIVE and _active_admins(db) <= 1:
            raise HTTPException(409, "Sekurang-kurangnya seorang Pentadbir KPT aktif diperlukan.")
        changes["status"] = (x.status, req.status)
        x.status = req.status
        if req.status == USER_INACTIVE:
            revoke_user_sessions(db, x.id)
    if req.can_verify is not None and req.can_verify != x.can_verify:
        changes["can_verify"] = (x.can_verify, req.can_verify)
        x.can_verify = req.can_verify
    if changes:
        db.add(AccountApproval(user_id=x.id, institution_id=x.institution_id, action="USER_UPDATED", actor_id=u.id,
                               reason=f"{reason} {json.dumps(changes, ensure_ascii=False, default=str)}"))
        audit(db, u, "user_updated", f"user:{x.id}", request, changes=changes, reason=reason)
        db.commit()
    return {"ok": True, "changes": changes}


# ------------------------------------------------------------------ institutions
class InstitutionIn(BaseModel):
    name: Optional[str] = Field(default=None, max_length=200)
    category: Optional[str] = None
    state: Optional[str] = None
    address: Optional[str] = Field(default=None, max_length=500)
    official_email: Optional[str] = Field(default=None, max_length=200)
    status: Optional[str] = None
    reason: str = Field(default="", max_length=500)


@router.patch("/admin/institutions/{iid}")
def update_institution(iid: int, req: InstitutionIn, request: Request, u: User = Depends(require("admin.institutions")),
                       db: Session = Depends(get_db)):
    inst = db.get(Institution, iid)
    if not inst:
        raise HTTPException(404, "Institusi tidak ditemui.")
    if len(_clean(req.reason, 500)) < 5:
        raise HTTPException(422, "Nyatakan sebab perubahan.")
    before = {"name": inst.name, "category": inst.category, "state": inst.state, "status": inst.status}
    if req.name is not None and _clean(req.name, 200):
        inst.name = _clean(req.name, 200)
    if req.category is not None:
        if req.category not in INSTITUTION_CATEGORIES:
            raise HTTPException(422, "Kategori tidak sah.")
        inst.category = req.category
    if req.state is not None:
        if req.state and req.state not in STATES:
            raise HTTPException(422, "Negeri tidak sah.")
        inst.state = req.state or None
    if req.address is not None:
        inst.address = _clean(req.address, 500) or None
    if req.official_email is not None:
        inst.official_email = normalise_email(req.official_email) if req.official_email.strip() else None
    if req.status is not None:
        if req.status not in ("ACTIVE", "INACTIVE"):
            raise HTTPException(422, "Status institusi mesti ACTIVE atau INACTIVE.")
        inst.status = req.status
    audit(db, u, "institution_updated", f"institution:{inst.id}", request, before=before, reason=req.reason)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ reporting periods
class PeriodIn(BaseModel):
    status: str
    opens_on: Optional[str] = Field(default=None, max_length=10)
    closes_on: Optional[str] = Field(default=None, max_length=10)
    note: Optional[str] = Field(default=None, max_length=500)


@router.put("/admin/periods/{year}")
def update_period(year: int, req: PeriodIn, request: Request, u: User = Depends(require("admin.periods")),
                  db: Session = Depends(get_db)):
    if year not in YEARS:
        raise HTTPException(422, "Tahun mesti 2026–2030.")
    if req.status not in ("PLANNED", "OPEN", "CLOSED"):
        raise HTTPException(422, "Status mesti PLANNED, OPEN atau CLOSED.")
    p = db.scalar(select(ReportingPeriod).where(ReportingPeriod.year == year))
    if p is None:
        p = ReportingPeriod(year=year)
        db.add(p)
    before = p.status
    p.status, p.opens_on, p.closes_on, p.note = req.status, req.opens_on or None, req.closes_on or None, req.note
    p.updated_by, p.updated_at = u.id, utcnow()
    audit(db, u, "period_updated", f"period:{year}", request, before=before, after=req.status)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ KPI targets & definitions
class TargetIn(BaseModel):
    year: int
    value: Optional[float] = None
    kind: str = "value"
    label: Optional[str] = Field(default=None, max_length=120)
    reason: str = Field(max_length=1000)


@router.put("/admin/kpis/{kpi_id}/targets")
def update_target(kpi_id: int, req: TargetIn, request: Request, u: User = Depends(require("admin.kpis")),
                  db: Session = Depends(get_db)):
    """Controlled change of an official annual target. Every change requires a reason and is audited."""
    k = db.get(Kpi, kpi_id)
    if not k or req.year not in YEARS:
        raise HTTPException(404, "KPI atau tahun tidak sah.")
    if len(_clean(req.reason, 1000)) < 10:
        raise HTTPException(422, "Nyatakan rujukan/justifikasi rasmi perubahan sasaran (≥10 aksara).")
    if req.kind not in ("value", "milestone"):
        raise HTTPException(422, "Jenis sasaran tidak sah.")
    if req.value is not None and req.value < 0:
        raise HTTPException(422, "Sasaran tidak boleh negatif.")
    t = db.scalar(select(Target).where(Target.kpi_id == k.id, Target.year == req.year))
    if t is None:
        t = Target(kpi_id=k.id, year=req.year)
        db.add(t)
    before = {"value": t.value, "kind": t.kind, "label": t.label}
    t.value, t.kind, t.label = req.value, req.kind, (req.label or None)
    t.updated_by, t.updated_at = u.id, utcnow()
    audit(db, u, "target_changed", f"kpi:{k.code}:{req.year}", request, before=before,
          after={"value": req.value, "kind": req.kind, "label": req.label}, reason=req.reason)
    db.commit()
    return {"ok": True}


class KpiTextIn(BaseModel):
    definition: Optional[str] = Field(default=None, max_length=4000)
    numerator_label: Optional[str] = Field(default=None, max_length=1000)
    denominator_label: Optional[str] = Field(default=None, max_length=1000)
    data_owner: Optional[str] = Field(default=None, max_length=1000)
    formula_status: Optional[str] = None
    reason: str = Field(max_length=1000)


@router.patch("/admin/kpis/{kpi_id}")
def update_kpi(kpi_id: int, req: KpiTextIn, request: Request, u: User = Depends(require("admin.kpis")),
               db: Session = Depends(get_db)):
    k = db.get(Kpi, kpi_id)
    if not k:
        raise HTTPException(404, "KPI tidak ditemui.")
    if len(_clean(req.reason, 1000)) < 10:
        raise HTTPException(422, "Nyatakan rujukan/justifikasi rasmi perubahan (≥10 aksara).")
    before = {f: getattr(k, f) for f in ("definition", "numerator_label", "denominator_label", "data_owner", "formula_status")}
    for f in ("definition", "numerator_label", "denominator_label", "data_owner"):
        v = getattr(req, f)
        if v is not None and v.strip():
            setattr(k, f, v.strip())
    if req.formula_status is not None:
        if req.formula_status not in ("draft", "confirmed"):
            raise HTTPException(422, "Status formula mesti draft atau confirmed.")
        k.formula_status = req.formula_status
    if k.unit == "percent":
        k.measurement = f"({k.numerator_label} ÷ {k.denominator_label}) × 100%"
    audit(db, u, "kpi_definition_changed", f"kpi:{k.code}", request, before=before, reason=req.reason)
    db.commit()
    return {"ok": True}


class InstTargetIn(BaseModel):
    institution_id: int
    kpi_id: int
    year: int
    value: Optional[float] = None
    reason: str = Field(max_length=1000)


@router.get("/admin/institution-targets")
def list_inst_targets(year: int, u: User = Depends(require("admin.kpis")), db: Session = Depends(get_db)):
    rows = db.scalars(select(InstitutionTarget).where(InstitutionTarget.year == year))
    return [{"id": t.id, "institution_id": t.institution_id, "kpi_id": t.kpi_id, "year": t.year, "value": t.value}
            for t in rows]


@router.put("/admin/institution-targets")
def set_inst_target(req: InstTargetIn, request: Request, u: User = Depends(require("admin.kpis")),
                    db: Session = Depends(get_db)):
    if len(_clean(req.reason, 1000)) < 10:
        raise HTTPException(422, "Nyatakan rujukan peruntukan sasaran institusi oleh KPT (≥10 aksara).")
    if req.year not in YEARS or not db.get(Kpi, req.kpi_id) or not db.get(Institution, req.institution_id):
        raise HTTPException(404, "Data tidak sah.")
    t = db.scalar(select(InstitutionTarget).where(InstitutionTarget.institution_id == req.institution_id,
                                                  InstitutionTarget.kpi_id == req.kpi_id, InstitutionTarget.year == req.year))
    before = t.value if t else None
    if req.value is None:
        if t:
            db.delete(t)
    else:
        if req.value < 0:
            raise HTTPException(422, "Sasaran tidak boleh negatif.")
        if t is None:
            t = InstitutionTarget(institution_id=req.institution_id, kpi_id=req.kpi_id, year=req.year, value=req.value)
            db.add(t)
        t.value, t.set_by, t.set_at = req.value, u.id, utcnow()
    audit(db, u, "institution_target_set", f"inst:{req.institution_id}:kpi:{req.kpi_id}:{req.year}", request,
          before=before, after=req.value, reason=req.reason)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ national milestones (Indeks Kepuasan Majikan)
class MilestoneIn(BaseModel):
    year: int
    progress_pct: float = Field(ge=0, le=100)
    note: str = Field(default="", max_length=2000)


@router.get("/milestones")
def list_milestones(u: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{"kpi_id": m.kpi_id, "year": m.year, "progress_pct": m.progress_pct, "note": m.note,
             "recorded_at": _iso(m.recorded_at)} for m in db.scalars(select(KpiMilestone))]


@router.put("/admin/kpis/{kpi_id}/milestone")
def record_milestone(kpi_id: int, req: MilestoneIn, request: Request, u: User = Depends(require("admin.milestones")),
                     db: Session = Depends(get_db)):
    t = db.scalar(select(Target).where(Target.kpi_id == kpi_id, Target.year == req.year))
    if not t or t.kind != "milestone":
        raise HTTPException(422, "Tahun ini bukan tahun milestone bagi KPI tersebut.")
    m = db.scalar(select(KpiMilestone).where(KpiMilestone.kpi_id == kpi_id, KpiMilestone.year == req.year))
    before = m.progress_pct if m else None
    if m is None:
        m = KpiMilestone(kpi_id=kpi_id, year=req.year, progress_pct=req.progress_pct, recorded_by=u.id)
        db.add(m)
    m.progress_pct, m.note, m.recorded_by, m.recorded_at = req.progress_pct, req.note.strip() or None, u.id, utcnow()
    audit(db, u, "milestone_recorded", f"kpi:{kpi_id}:{req.year}", request, before=before, after=req.progress_pct)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ audit & settings
@router.get("/admin/audit")
def audit_log(q: str = "", event: str = "", limit: int = 300, u: User = Depends(require("admin.audit")),
              db: Session = Depends(get_db)):
    query = select(Audit)
    if event:
        query = query.where(Audit.event == event)
    if q.strip():
        like = f"%{q.strip().lower()}%"
        query = query.where(or_(func.lower(Audit.record).like(like), func.lower(Audit.detail).like(like)))
    rows = db.scalars(query.order_by(Audit.id.desc()).limit(min(limit, 2000)))
    names = {x.id: x.name for x in db.scalars(select(User))}
    return [{"id": a.id, "at": _iso(a.at), "actor": names.get(a.actor_id, "—") if a.actor_id else "Awam/sistem",
             "event": a.event, "record": a.record, "ip": a.ip_address, "detail": a.detail} for a in rows]


@router.get("/admin/settings")
def get_settings(u: User = Depends(require("admin.settings")), db: Session = Depends(get_db)):
    return {k: get_setting(db, k) for k in SETTING_DEFAULTS} | {
        "smtp_enabled": settings.smtp_enabled, "environment": settings.env, "max_upload_mb": settings.max_upload_mb,
        "invitation_hours": settings.invitation_hours}


class SettingsIn(BaseModel):
    pilot_notice_enabled: Optional[bool] = None
    pilot_notice: Optional[str] = Field(default=None, max_length=2000)
    evidence_required_on_submit: Optional[bool] = None
    default_reporting_year: Optional[int] = None


@router.put("/admin/settings")
def put_settings(req: SettingsIn, request: Request, u: User = Depends(require("admin.settings")),
                 db: Session = Depends(get_db)):
    changed = {}
    if req.pilot_notice_enabled is not None:
        set_setting(db, "pilot_notice_enabled", "true" if req.pilot_notice_enabled else "false", u)
        changed["pilot_notice_enabled"] = req.pilot_notice_enabled
    if req.pilot_notice is not None:
        if not req.pilot_notice.strip():
            raise HTTPException(422, "Teks notis tidak boleh kosong.")
        set_setting(db, "pilot_notice", req.pilot_notice.strip(), u)
        changed["pilot_notice"] = True
    if req.evidence_required_on_submit is not None:
        set_setting(db, "evidence_required_on_submit", "true" if req.evidence_required_on_submit else "false", u)
        changed["evidence_required_on_submit"] = req.evidence_required_on_submit
    if req.default_reporting_year is not None:
        if req.default_reporting_year not in YEARS:
            raise HTTPException(422, "Tahun tidak sah.")
        set_setting(db, "default_reporting_year", str(req.default_reporting_year), u)
        changed["default_reporting_year"] = req.default_reporting_year
    audit(db, u, "settings_changed", "settings", request, **changed)
    db.commit()
    return {"ok": True}
