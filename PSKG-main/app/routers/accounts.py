"""Penyelaras KPT account management: application approval, pre-registration, IPT accounts."""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..config import INSTITUTION_CATEGORIES, STATES, settings
from ..db import get_db
from ..models import (APP_APPROVED, APP_PENDING, APP_REJECTED, ROLE_IPT, USER_ACTIVE, USER_INACTIVE, USER_INVITED,
                      USER_PENDING, USER_REJECTED, AccountApproval, AccountInvitation, EmailOutbox, Institution,
                      RegistrationApplication, User, utcnow)
from ..security import aware, digest, new_token, normalise_email, require, revoke_user_sessions
from ..services import audit, institution_user_ids, link, notify, send_email
from .public import APP_STATUS_LABEL, _clean, _phone

router = APIRouter(prefix="/api/kpt")


def _iso(dt):
    return aware(dt).isoformat() if dt else None


def _user_name(db: Session, uid: Optional[int]) -> Optional[str]:
    u = db.get(User, uid) if uid else None
    return u.name if u else None


def _find_institution(db: Session, code: str, name: str) -> Optional[Institution]:
    return db.scalar(select(Institution).where(or_(func.upper(Institution.code) == code.upper(),
                                                   func.lower(Institution.name) == name.lower())))


# ------------------------------------------------------------------ applications
@router.get("/applications")
def list_applications(status: str = "", q: str = "", u: User = Depends(require("accounts.review")),
                      db: Session = Depends(get_db)):
    query = select(RegistrationApplication)
    if status:
        query = query.where(RegistrationApplication.status == status)
    if q.strip():
        like = f"%{q.strip().lower()}%"
        query = query.where(or_(func.lower(RegistrationApplication.inst_name).like(like),
                                func.lower(RegistrationApplication.inst_code).like(like),
                                func.lower(RegistrationApplication.coordinator_name).like(like),
                                func.lower(RegistrationApplication.account_email).like(like),
                                func.lower(RegistrationApplication.ref_no).like(like)))
    rows = db.scalars(query.order_by(RegistrationApplication.submitted_at.desc()))
    return [{"id": a.id, "ref_no": a.ref_no, "inst_name": a.inst_name, "inst_code": a.inst_code,
             "inst_category": INSTITUTION_CATEGORIES.get(a.inst_category or "", a.inst_category or "—"),
             "coordinator_name": a.coordinator_name, "email": a.account_email, "submitted_at": _iso(a.submitted_at),
             "status": a.status, "status_label": APP_STATUS_LABEL.get(a.status, a.status), "source": a.source}
            for a in rows]


@router.get("/applications/{app_id}")
def application_detail(app_id: int, u: User = Depends(require("accounts.review")), db: Session = Depends(get_db)):
    a = db.get(RegistrationApplication, app_id)
    if not a:
        raise HTTPException(404, "Permohonan tidak ditemui.")
    existing_inst = db.get(Institution, a.institution_id) if a.institution_id else _find_institution(db, a.inst_code, a.inst_name)
    checks = []
    if existing_inst:
        active_users = db.scalars(select(User).where(User.institution_id == existing_inst.id, User.status == USER_ACTIVE,
                                                     User.role == ROLE_IPT)).all()
        checks.append(f"Institusi wujud dalam direktori ({existing_inst.code}, status {existing_inst.status}).")
        if active_users:
            checks.append("Akaun Penyelaras IPT aktif sedia ada bagi institusi ini: "
                          + ", ".join(f"{x.name} <{x.email}>" for x in active_users))
    else:
        checks.append("Institusi baharu — rekod institusi akan diwujudkan apabila permohonan diluluskan.")
    others = db.scalars(select(RegistrationApplication).where(
        RegistrationApplication.id != a.id,
        or_(func.upper(RegistrationApplication.inst_code) == a.inst_code.upper(),
            func.lower(RegistrationApplication.account_email) == a.account_email.lower()))).all()
    for o in others:
        checks.append(f"Permohonan lain berkaitan: {o.ref_no} ({APP_STATUS_LABEL.get(o.status, o.status)}).")
    if a.official_email and a.inst_email and a.official_email.split("@")[-1] != a.inst_email.split("@")[-1]:
        checks.append("Domain emel pegawai berbeza daripada domain emel rasmi institusi — sahkan identiti pemohon.")
    if a.official_email and a.account_email.split("@")[-1] != a.official_email.split("@")[-1]:
        checks.append("Emel pengguna bukan domain yang sama dengan emel rasmi pegawai.")
    history = db.scalars(select(AccountApproval).where(AccountApproval.application_id == a.id)
                         .order_by(AccountApproval.at)).all()
    return {
        "id": a.id, "ref_no": a.ref_no, "status": a.status, "status_label": APP_STATUS_LABEL.get(a.status, a.status),
        "source": a.source, "submitted_at": _iso(a.submitted_at),
        "institution": {"existing_id": existing_inst.id if existing_inst else None, "name": a.inst_name,
                        "code": a.inst_code, "category": a.inst_category,
                        "category_label": INSTITUTION_CATEGORIES.get(a.inst_category or "", "—"),
                        "address": a.inst_address, "state": a.inst_state, "email": a.inst_email},
        "coordinator": {"name": a.coordinator_name, "position": a.position, "department": a.department,
                        "official_email": a.official_email, "phone": a.phone, "account_email": a.account_email},
        "decided_by": _user_name(db, a.decided_by), "decided_at": _iso(a.decided_at), "reason": a.decision_reason,
        "checks": checks,
        "history": [{"action": h.action, "actor": _user_name(db, h.actor_id), "reason": h.reason, "at": _iso(h.at)}
                    for h in history],
    }


class DecisionIn(BaseModel):
    reason: str = Field(default="", max_length=1000)
    category: Optional[str] = Field(default=None, max_length=20)


@router.post("/applications/{app_id}/approve")
def approve_application(app_id: int, req: DecisionIn, request: Request, u: User = Depends(require("accounts.review")),
                        db: Session = Depends(get_db)):
    a = db.get(RegistrationApplication, app_id)
    if not a:
        raise HTTPException(404, "Permohonan tidak ditemui.")
    if a.status != APP_PENDING:
        raise HTTPException(409, "Permohonan ini telah diputuskan.")
    user = db.get(User, a.user_id) if a.user_id else None
    if not user or user.status != USER_PENDING:
        raise HTTPException(409, "Akaun pemohon tidak lagi dalam status menunggu kelulusan.")
    inst = db.get(Institution, a.institution_id) if a.institution_id else _find_institution(db, a.inst_code, a.inst_name)
    category = (req.category or a.inst_category or "").upper() or None
    if category and category not in INSTITUTION_CATEGORIES:
        raise HTTPException(422, "Kategori institusi tidak sah.")
    if inst is None:
        inst = Institution(name=a.inst_name, code=a.inst_code, status="ACTIVE", category=category,
                           address=a.inst_address, state=a.inst_state, official_email=a.inst_email,
                           created_via="SELF_REGISTRATION")
        db.add(inst)
        db.flush()
    else:
        if inst.status != "ACTIVE":
            inst.status = "ACTIVE"
        inst.category = inst.category or category
        inst.address = inst.address or a.inst_address
        inst.state = inst.state or a.inst_state
        inst.official_email = inst.official_email or a.inst_email
    user.institution_id = inst.id
    user.status = USER_ACTIVE
    user.role = ROLE_IPT
    user.activated_at = utcnow()
    a.status, a.institution_id, a.decided_by, a.decided_at = APP_APPROVED, inst.id, u.id, utcnow()
    a.decision_reason = _clean(req.reason, 1000) or None
    db.add(AccountApproval(application_id=a.id, user_id=user.id, institution_id=inst.id, action="APPROVED",
                           actor_id=u.id, reason=a.decision_reason))
    audit(db, u, "registration_approved", f"application:{a.id}", request, user_id=user.id, institution_id=inst.id)
    notify(db, [user.id], "REGISTRATION_APPROVED", "Permohonan akaun diluluskan",
           f"Akaun Penyelaras IPT bagi {inst.name} telah diluluskan.", "#/ipt")
    send_email(db, user.email, "PSKG Monitor 2030: Permohonan akaun diluluskan",
               f"Salam {user.name},\n\nPermohonan {a.ref_no} bagi {inst.name} telah DILULUSKAN oleh Penyelaras KPT.\n"
               f"Anda kini boleh log masuk: {link('#/login')}\n", kind="REGISTRATION_APPROVED")
    db.commit()
    return {"status": a.status, "status_label": APP_STATUS_LABEL[a.status], "institution_id": inst.id}


@router.post("/applications/{app_id}/reject")
def reject_application(app_id: int, req: DecisionIn, request: Request, u: User = Depends(require("accounts.review")),
                       db: Session = Depends(get_db)):
    a = db.get(RegistrationApplication, app_id)
    if not a:
        raise HTTPException(404, "Permohonan tidak ditemui.")
    if a.status != APP_PENDING:
        raise HTTPException(409, "Permohonan ini telah diputuskan.")
    reason = _clean(req.reason, 1000)
    if len(reason) < 5:
        raise HTTPException(422, "Sebab penolakan wajib dinyatakan.")
    user = db.get(User, a.user_id) if a.user_id else None
    if user and user.status == USER_PENDING:
        user.status = USER_REJECTED
    if a.institution_id:
        inst = db.get(Institution, a.institution_id)
        if inst and inst.status == "PENDING":  # legacy V2B pending institution
            inst.status = "REJECTED"
    a.status, a.decided_by, a.decided_at, a.decision_reason = APP_REJECTED, u.id, utcnow(), reason
    db.add(AccountApproval(application_id=a.id, user_id=a.user_id, institution_id=a.institution_id,
                           action="REJECTED", actor_id=u.id, reason=reason))
    audit(db, u, "registration_rejected", f"application:{a.id}", request, reason=reason)
    if user:
        notify(db, [user.id], "REGISTRATION_REJECTED", "Permohonan akaun ditolak", reason)
        send_email(db, user.email, "PSKG Monitor 2030: Permohonan akaun ditolak",
                   f"Salam {user.name},\n\nPermohonan {a.ref_no} telah DITOLAK.\nSebab: {reason}\n",
                   kind="REGISTRATION_REJECTED")
    db.commit()
    return {"status": a.status, "status_label": APP_STATUS_LABEL[a.status]}


# ------------------------------------------------------------------ pre-registration
class PreRegisterIn(BaseModel):
    existing_institution_id: Optional[int] = None
    inst_name: str = Field(default="", max_length=200)
    inst_code: str = Field(default="", max_length=40)
    inst_category: str = Field(default="", max_length=20)
    inst_state: str = Field(default="", max_length=60)
    inst_address: str = Field(default="", max_length=500)
    inst_email: str = Field(default="", max_length=200)
    name: str = Field(max_length=150)
    email: str = Field(max_length=200)
    position: str = Field(max_length=150)
    department: str = Field(max_length=150)
    phone: str = Field(max_length=40)


def _issue_invitation(db: Session, user: User, actor: User) -> tuple[str, AccountInvitation]:
    for old in db.scalars(select(AccountInvitation).where(AccountInvitation.user_id == user.id,
                                                          AccountInvitation.purpose == "ACTIVATION",
                                                          AccountInvitation.used_at.is_(None),
                                                          AccountInvitation.revoked_at.is_(None))):
        old.revoked_at = utcnow()
    token = new_token()
    inv = AccountInvitation(user_id=user.id, institution_id=user.institution_id, purpose="ACTIVATION",
                            token_digest=digest(token), created_by=actor.id,
                            expires_at=utcnow() + timedelta(hours=settings.invitation_hours))
    db.add(inv)
    inst = db.get(Institution, user.institution_id) if user.institution_id else None
    send_email(db, user.email, "PSKG Monitor 2030: Jemputan pengaktifan akaun Penyelaras IPT",
               f"Salam {user.name},\n\nPenyelaras KPT telah mendaftarkan akaun Penyelaras IPT untuk anda bagi "
               f"{inst.name if inst else '-'}.\n\nSila sahkan maklumat dan tetapkan kata laluan anda melalui pautan "
               f"sekali guna berikut (sah selama {settings.invitation_hours} jam):\n{link('#/aktif?token=' + token)}\n\n"
               f"Kata laluan tidak akan dihantar melalui emel.\n", kind="INVITATION")
    return token, inv


def _dev_link(token: str) -> Optional[str]:
    # Only exposed while SMTP is not configured (development preview) — never in production.
    if settings.smtp_enabled or settings.env == "production":
        return None
    return link("#/aktif?token=" + token)


@router.post("/preregister", status_code=201)
def preregister(req: PreRegisterIn, request: Request, u: User = Depends(require("accounts.preregister")),
                db: Session = Depends(get_db)):
    email = normalise_email(req.email)
    name, position, department = _clean(req.name, 150), _clean(req.position, 150), _clean(req.department, 150)
    if len(name) < 3 or not position or not department:
        raise HTTPException(422, "Nama, jawatan dan bahagian/jabatan penyelaras wajib diisi.")
    phone = _phone(req.phone)
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(409, "Emel ini telah mempunyai akaun. Gunakan 'Senarai Akaun IPT' untuk mengurus akaun "
                                 "sedia ada atau hantar semula jemputan.")
    if req.existing_institution_id:
        inst = db.get(Institution, req.existing_institution_id)
        if not inst:
            raise HTTPException(404, "Institusi tidak ditemui.")
        if inst.status != "ACTIVE":
            inst.status = "ACTIVE"
    else:
        inst_name = _clean(req.inst_name, 200)
        code = _clean(req.inst_code, 40).upper().replace(" ", "")
        cat = req.inst_category.strip().upper()
        if len(inst_name) < 3 or len(code) < 2:
            raise HTTPException(422, "Nama rasmi IPT dan kod IPT wajib diisi.")
        if cat not in INSTITUTION_CATEGORIES:
            raise HTTPException(422, "Sila pilih kategori IPT.")
        if req.inst_state and req.inst_state not in STATES:
            raise HTTPException(422, "Negeri tidak sah.")
        if _find_institution(db, code, inst_name):
            raise HTTPException(409, "Institusi dengan kod atau nama ini telah wujud. Pilih institusi sedia ada.")
        inst = Institution(name=inst_name, code=code, status="ACTIVE", category=cat, state=req.inst_state or None,
                           address=_clean(req.inst_address, 500) or None,
                           official_email=normalise_email(req.inst_email) if req.inst_email.strip() else None,
                           created_via="PRE_REGISTRATION")
        db.add(inst)
        db.flush()
    user = User(email=email, name=name, password_digest=None, role=ROLE_IPT, institution_id=inst.id,
                status=USER_INVITED, position=position, department=department, phone=phone, official_email=email)
    db.add(user)
    db.flush()
    token, inv = _issue_invitation(db, user, u)
    db.add(AccountApproval(user_id=user.id, institution_id=inst.id, action="PRE_REGISTERED", actor_id=u.id,
                           reason="Pra-daftar oleh Penyelaras KPT (pendaftaran dibenarkan KPT)"))
    audit(db, u, "account_preregistered", f"user:{user.id}", request, institution_id=inst.id)
    db.commit()
    return {"message": "Akaun telah dipra-daftar dan jemputan pengaktifan dihantar.", "user_id": user.id,
            "institution_id": inst.id, "expires_at": _iso(inv.expires_at), "email_delivery": (
                "SMTP" if settings.smtp_enabled else "DEV_PREVIEW"), "dev_activation_link": _dev_link(token)}


# ------------------------------------------------------------------ IPT accounts
@router.get("/accounts")
def list_accounts(status: str = "", q: str = "", u: User = Depends(require("accounts.manage")),
                  db: Session = Depends(get_db)):
    query = select(User).where(User.role == ROLE_IPT)
    if status:
        query = query.where(User.status == status)
    if q.strip():
        like = f"%{q.strip().lower()}%"
        query = query.where(or_(func.lower(User.name).like(like), func.lower(User.email).like(like)))
    out = []
    for x in db.scalars(query.order_by(User.name)):
        inst = db.get(Institution, x.institution_id) if x.institution_id else None
        inv = db.scalar(select(AccountInvitation).where(AccountInvitation.user_id == x.id,
                                                        AccountInvitation.purpose == "ACTIVATION")
                        .order_by(AccountInvitation.created_at.desc()))
        inv_state = None
        if inv:
            inv_state = ("DIGUNAKAN" if inv.used_at else "DIBATALKAN" if inv.revoked_at else
                         "TAMAT TEMPOH" if aware(inv.expires_at) < utcnow() else "AKTIF")
        out.append({"id": x.id, "name": x.name, "email": x.email, "status": x.status, "position": x.position,
                    "department": x.department, "phone": x.phone,
                    "institution": {"id": inst.id, "code": inst.code, "name": inst.name, "status": inst.status} if inst else None,
                    "activated_at": _iso(x.activated_at), "last_login_at": _iso(x.last_login_at),
                    "invitation": {"state": inv_state, "expires_at": _iso(inv.expires_at), "used_at": _iso(inv.used_at)} if inv else None})
    return out


class AccountActionIn(BaseModel):
    reason: str = Field(default="", max_length=1000)
    institution_id: Optional[int] = None


@router.post("/accounts/{user_id}/deactivate")
def deactivate(user_id: int, req: AccountActionIn, request: Request, u: User = Depends(require("accounts.manage")),
               db: Session = Depends(get_db)):
    x = db.get(User, user_id)
    if not x or x.role != ROLE_IPT:
        raise HTTPException(404, "Akaun IPT tidak ditemui.")
    reason = _clean(req.reason, 1000)
    if len(reason) < 5:
        raise HTTPException(422, "Nyatakan sebab penyahaktifan.")
    if x.status not in (USER_ACTIVE, USER_INVITED):
        raise HTTPException(409, "Akaun ini tidak aktif.")
    x.status = USER_INACTIVE
    revoke_user_sessions(db, x.id)
    for inv in db.scalars(select(AccountInvitation).where(AccountInvitation.user_id == x.id,
                                                          AccountInvitation.used_at.is_(None),
                                                          AccountInvitation.revoked_at.is_(None))):
        inv.revoked_at = utcnow()
    db.add(AccountApproval(user_id=x.id, institution_id=x.institution_id, action="DEACTIVATED", actor_id=u.id, reason=reason))
    audit(db, u, "account_deactivated", f"user:{x.id}", request, reason=reason)
    db.commit()
    return {"status": x.status}


@router.post("/accounts/{user_id}/reactivate")
def reactivate(user_id: int, req: AccountActionIn, request: Request, u: User = Depends(require("accounts.manage")),
               db: Session = Depends(get_db)):
    x = db.get(User, user_id)
    if not x or x.role != ROLE_IPT:
        raise HTTPException(404, "Akaun IPT tidak ditemui.")
    if x.status != USER_INACTIVE:
        raise HTTPException(409, "Hanya akaun yang dinyahaktifkan boleh diaktifkan semula.")
    x.status = USER_ACTIVE if x.password_digest else USER_INVITED
    db.add(AccountApproval(user_id=x.id, institution_id=x.institution_id, action="REACTIVATED", actor_id=u.id,
                           reason=_clean(req.reason, 1000) or None))
    audit(db, u, "account_reactivated", f"user:{x.id}", request)
    db.commit()
    return {"status": x.status}


@router.post("/accounts/{user_id}/institution")
def reassign(user_id: int, req: AccountActionIn, request: Request, u: User = Depends(require("accounts.manage")),
             db: Session = Depends(get_db)):
    x = db.get(User, user_id)
    inst = db.get(Institution, req.institution_id) if req.institution_id else None
    if not x or x.role != ROLE_IPT or not inst:
        raise HTTPException(404, "Akaun atau institusi tidak ditemui.")
    reason = _clean(req.reason, 1000)
    if len(reason) < 5:
        raise HTTPException(422, "Nyatakan sebab penukaran institusi.")
    old = x.institution_id
    x.institution_id = inst.id
    revoke_user_sessions(db, x.id)
    db.add(AccountApproval(user_id=x.id, institution_id=inst.id, action="INSTITUTION_CHANGED", actor_id=u.id,
                           reason=f"{reason} (dari institusi #{old})"))
    audit(db, u, "account_institution_changed", f"user:{x.id}", request, old=old, new=inst.id)
    db.commit()
    return {"institution_id": inst.id}


@router.post("/accounts/{user_id}/reissue")
def reissue(user_id: int, request: Request, u: User = Depends(require("accounts.preregister")),
            db: Session = Depends(get_db)):
    x = db.get(User, user_id)
    if not x or x.role != ROLE_IPT:
        raise HTTPException(404, "Akaun IPT tidak ditemui.")
    if x.status != USER_INVITED:
        raise HTTPException(409, "Jemputan hanya boleh dihantar semula bagi akaun yang belum diaktifkan.")
    token, inv = _issue_invitation(db, x, u)
    db.add(AccountApproval(user_id=x.id, institution_id=x.institution_id, action="INVITATION_REISSUED", actor_id=u.id))
    audit(db, u, "invitation_reissued", f"user:{x.id}", request)
    db.commit()
    return {"message": "Jemputan baharu dihantar; jemputan terdahulu dibatalkan.", "expires_at": _iso(inv.expires_at),
            "dev_activation_link": _dev_link(token)}


@router.get("/history")
def approval_history(limit: int = 300, u: User = Depends(require("accounts.review")), db: Session = Depends(get_db)):
    rows = db.scalars(select(AccountApproval).order_by(AccountApproval.at.desc()).limit(min(limit, 1000)))
    out = []
    for h in rows:
        target = db.get(User, h.user_id) if h.user_id else None
        inst = db.get(Institution, h.institution_id) if h.institution_id else None
        app = db.get(RegistrationApplication, h.application_id) if h.application_id else None
        out.append({"at": _iso(h.at), "action": h.action, "actor": _user_name(db, h.actor_id) or "Pemohon / sistem",
                    "user": f"{target.name} <{target.email}>" if target else (app.account_email if app else None),
                    "institution": inst.name if inst else (app.inst_name if app else None),
                    "ref_no": app.ref_no if app else None, "reason": h.reason})
    return out


@router.get("/institutions")
def institutions(u: User = Depends(require("accounts.manage", "monitoring.view")), db: Session = Depends(get_db)):
    out = []
    for i in db.scalars(select(Institution).order_by(Institution.name)):
        n_active = db.scalar(select(func.count()).select_from(User).where(User.institution_id == i.id,
                                                                          User.status == USER_ACTIVE)) or 0
        out.append({"id": i.id, "code": i.code, "name": i.name, "category": i.category,
                    "category_label": INSTITUTION_CATEGORIES.get(i.category or "", "—"), "state": i.state,
                    "status": i.status, "active_users": n_active, "is_demo": i.is_demo, "created_via": i.created_via})
    return out


@router.get("/outbox")
def email_outbox(u: User = Depends(require("notifications.outbox")), db: Session = Depends(get_db)):
    """Development-only preview of e-mails that were NOT delivered because SMTP is not configured."""
    rows = db.scalars(select(EmailOutbox).order_by(EmailOutbox.created_at.desc()).limit(200))
    return {"smtp_enabled": settings.smtp_enabled,
            "items": [{"id": e.id, "to": e.to_email, "subject": e.subject,
                       "body": e.body if (e.status == "DEV_PREVIEW" and settings.env != "production") else
                       "[kandungan disembunyikan]", "status": e.status, "kind": e.kind, "created_at": _iso(e.created_at)}
                      for e in rows]}
