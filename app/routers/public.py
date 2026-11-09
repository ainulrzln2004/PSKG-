"""Public endpoints: configuration, login/logout, self-registration, status check,
account activation and password reset."""
from __future__ import annotations

import secrets
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import INSTITUTION_CATEGORIES, STATES, YEARS, settings
from ..db import get_db
from ..models import (APP_PENDING, ROLE_IPT, ROLES, USER_ACTIVE, USER_INVITED, USER_PENDING, AccountApproval,
                      AccountInvitation, Institution, LoginSession, RegistrationApplication, User, utcnow)
from ..security import (SESSION_COOKIE, account_block_reason, aware, client_ip, create_session, current_session,
                        current_user, digest, login_blocked, new_token, normalise_email, password_hash,
                        permissions_of, record_login_attempt, revoke_user_sessions, throttle, validate_password,
                        verify_password)
from ..services import audit, get_setting, kpt_reviewer_ids, link, notify, send_email, setting_bool

router = APIRouter(prefix="/api")

APP_STATUS_LABEL = {"PENDING_APPROVAL": "Menunggu Kelulusan", "APPROVED": "Diluluskan", "REJECTED": "Ditolak"}


def _clean(s: Optional[str], n: int = 200) -> str:
    return " ".join((s or "").split())[:n]


@router.get("/public/config")
def public_config(db: Session = Depends(get_db)):
    return {
        "pilot_notice_enabled": setting_bool(db, "pilot_notice_enabled"),
        "pilot_notice": get_setting(db, "pilot_notice"),
        "categories": INSTITUTION_CATEGORIES,
        "states": STATES,
        "years": YEARS,
        "default_year": int(get_setting(db, "default_reporting_year") or 2026),
        "smtp_enabled": settings.smtp_enabled,
        "environment": settings.env,
        "max_upload_mb": settings.max_upload_mb,
    }


@router.get("/public/institutions")
def institution_directory(q: str = "", db: Session = Depends(get_db)):
    """Directory of ACTIVE institutions so applicants can select an existing record."""
    q = _clean(q, 80)
    if len(q) < 2:
        return []
    like = f"%{q.lower()}%"
    rows = db.scalars(select(Institution).where(Institution.status == "ACTIVE", Institution.is_demo.is_(False),
                      (func.lower(Institution.name).like(like)) | (func.lower(Institution.code).like(like)))
                      .order_by(Institution.name).limit(15))
    return [{"id": i.id, "code": i.code, "name": i.name, "category": i.category} for i in rows]


# ------------------------------------------------------------------ login
class LoginIn(BaseModel):
    email: str = Field(max_length=200)
    password: str = Field(max_length=200)


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(SESSION_COOKIE, token, httponly=True, secure=settings.cookie_secure, samesite="strict",
                        max_age=settings.session_hours * 3600, path="/")


def me_payload(db: Session, u: User) -> dict:
    inst = db.get(Institution, u.institution_id) if u.institution_id else None
    return {"id": u.id, "name": u.name, "email": u.email, "role": u.role, "role_label": ROLES.get(u.role, u.role),
            "institution": {"id": inst.id, "code": inst.code, "name": inst.name, "category": inst.category} if inst else None,
            "permissions": permissions_of(u), "can_verify": bool(u.can_verify)}


@router.post("/login")
def login(req: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    email = (req.email or "").strip().lower()
    ip = client_ip(request)
    if login_blocked(db, email, ip):
        audit(db, None, "login_blocked", f"email:{email}", request)
        db.commit()
        raise HTTPException(429, f"Terlalu banyak cubaan log masuk gagal. Sila cuba semula selepas "
                                 f"{settings.login_window_minutes} minit atau tetapkan semula kata laluan.")
    u = db.scalar(select(User).where(User.email == email))
    if not u or not verify_password(req.password, u.password_digest):
        record_login_attempt(db, email, ip, False)
        audit(db, None, "login_failed", f"email:{email}", request)
        db.commit()
        raise HTTPException(401, "Emel atau kata laluan tidak sah.")
    # Credentials are correct: it is safe to explain why the account cannot be used yet.
    reason = account_block_reason(db, u)
    if reason:
        record_login_attempt(db, email, ip, False)
        audit(db, u, "login_denied", f"user:{u.id}", request, status=u.status)
        db.commit()
        raise HTTPException(403, reason)
    record_login_attempt(db, email, ip, True)
    token = create_session(db, u, request)
    u.last_login_at = utcnow()
    audit(db, u, "login", f"user:{u.id}", request)
    db.commit()
    _set_cookie(response, token)
    return {"user": me_payload(db, u)}


@router.post("/logout")
def logout(request: Request, response: Response, s: LoginSession = Depends(current_session),
           db: Session = Depends(get_db)):
    u = db.get(User, s.user_id)
    db.delete(s)
    audit(db, u, "logout", f"user:{s.user_id}", request)
    db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(u: User = Depends(current_user), db: Session = Depends(get_db)):
    return me_payload(db, u)


class PasswordChangeIn(BaseModel):
    current_password: str = Field(max_length=200)
    new_password: str = Field(max_length=200)
    confirm_password: str = Field(max_length=200)


@router.post("/me/password")
def change_password(req: PasswordChangeIn, request: Request, response: Response, u: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    if not verify_password(req.current_password, u.password_digest):
        raise HTTPException(422, "Kata laluan semasa tidak tepat.")
    validate_password(req.new_password, req.confirm_password, u.email)
    u.password_digest = password_hash.hash(req.new_password)
    u.password_changed_at = utcnow()
    revoke_user_sessions(db, u.id)
    token = create_session(db, u, request)
    audit(db, u, "password_changed", f"user:{u.id}", request)
    db.commit()
    _set_cookie(response, token)
    return {"message": "Kata laluan telah ditukar."}


# ------------------------------------------------------------------ self-registration
class RegistrationIn(BaseModel):
    existing_institution_id: Optional[int] = None
    inst_name: str = Field(default="", max_length=200)
    inst_code: str = Field(default="", max_length=40)
    inst_category: str = Field(default="", max_length=20)
    inst_address: str = Field(default="", max_length=500)
    inst_state: str = Field(default="", max_length=60)
    inst_email: str = Field(default="", max_length=200)
    coordinator_name: str = Field(max_length=150)
    position: str = Field(max_length=150)
    department: str = Field(max_length=150)
    official_email: str = Field(max_length=200)
    phone: str = Field(max_length=40)
    account_email: str = Field(max_length=200)
    password: str = Field(max_length=200)
    confirm_password: str = Field(max_length=200)


def _phone(v: str) -> str:
    v = _clean(v, 40)
    digits = [c for c in v if c.isdigit()]
    if len(digits) < 7 or any(c not in "0123456789+-() " for c in v):
        raise HTTPException(422, "Nombor telefon pejabat tidak sah.")
    return v


def new_ref(db: Session) -> str:
    for _ in range(20):
        ref = f"REG-{utcnow().year}-{secrets.token_hex(3).upper()}"
        if not db.scalar(select(RegistrationApplication.id).where(RegistrationApplication.ref_no == ref)):
            return ref
    raise HTTPException(500, "Gagal menjana nombor permohonan.")


@router.post("/register", status_code=201)
def register(req: RegistrationIn, request: Request, db: Session = Depends(get_db)):
    throttle(db, "register", client_ip(request), settings.public_form_limit)
    name = _clean(req.coordinator_name, 150)
    if len(name) < 3:
        raise HTTPException(422, "Nama penuh penyelaras wajib diisi.")
    position, department = _clean(req.position, 150), _clean(req.department, 150)
    if not position or not department:
        raise HTTPException(422, "Jawatan dan Bahagian/Jabatan wajib diisi.")
    official_email = normalise_email(req.official_email)
    account_email = normalise_email(req.account_email)
    phone = _phone(req.phone)
    validate_password(req.password, req.confirm_password, account_email)

    inst: Optional[Institution] = None
    if req.existing_institution_id:
        inst = db.get(Institution, req.existing_institution_id)
        if not inst or inst.status != "ACTIVE":
            raise HTTPException(422, "Institusi yang dipilih tidak ditemui dalam direktori.")
        inst_name, inst_code, category = inst.name, inst.code, inst.category
        address, state, inst_email = inst.address, inst.state, inst.official_email
    else:
        inst_name = _clean(req.inst_name, 200)
        inst_code = _clean(req.inst_code, 40).upper().replace(" ", "")
        category = req.inst_category.strip().upper()
        address, state = _clean(req.inst_address, 500), _clean(req.inst_state, 60)
        if len(inst_name) < 3 or len(inst_code) < 2:
            raise HTTPException(422, "Nama rasmi IPT dan kod institusi wajib diisi.")
        if category not in INSTITUTION_CATEGORIES:
            raise HTTPException(422, "Sila pilih kategori IPT.")
        if not address:
            raise HTTPException(422, "Alamat institusi wajib diisi.")
        if state not in STATES:
            raise HTTPException(422, "Sila pilih negeri.")
        inst_email = normalise_email(req.inst_email)
        dup = db.scalar(select(Institution).where((func.upper(Institution.code) == inst_code) |
                                                  (func.lower(Institution.name) == inst_name.lower())))
        if dup and dup.status == "ACTIVE":
            raise HTTPException(409, "Institusi ini telah berdaftar. Sila pilih institusi daripada direktori "
                                     "('Pilih institusi sedia ada').")
        if dup and dup.status in ("PENDING",):
            inst = None  # legacy pending institution: decided together with its application

    if db.scalar(select(User.id).where(User.email == account_email)):
        raise HTTPException(409, "Emel pengguna ini telah digunakan. Gunakan 'Lupa kata laluan' atau "
                                 "'Semak status permohonan'.")
    pending_dup = db.scalar(select(RegistrationApplication).where(
        RegistrationApplication.status == APP_PENDING,
        (func.upper(RegistrationApplication.inst_code) == inst_code.upper()) |
        (func.lower(RegistrationApplication.inst_name) == inst_name.lower())))
    if pending_dup:
        raise HTTPException(409, "Permohonan bagi institusi ini sedang menunggu kelulusan Penyelaras KPT. "
                                 "Permohonan berganda tidak dibenarkan.")

    user = User(email=account_email, name=name, password_digest=password_hash.hash(req.password), role=ROLE_IPT,
                institution_id=None, status=USER_PENDING, position=position, department=department, phone=phone,
                official_email=official_email)
    db.add(user)
    db.flush()
    status_code = secrets.token_hex(4).upper()
    app = RegistrationApplication(
        ref_no=new_ref(db), status=APP_PENDING, institution_id=inst.id if inst else None, inst_name=inst_name,
        inst_code=inst_code, inst_category=category, inst_address=address, inst_state=state, inst_email=inst_email,
        coordinator_name=name, position=position, department=department, official_email=official_email,
        phone=phone, account_email=account_email, user_id=user.id, status_code_digest=digest(status_code),
        ip_address=client_ip(request)[:64])
    db.add(app)
    db.flush()
    db.add(AccountApproval(application_id=app.id, user_id=user.id, institution_id=app.institution_id,
                           action="SUBMITTED", actor_id=None, reason=None))
    audit(db, None, "registration_submitted", f"application:{app.id}", request, ref_no=app.ref_no,
          institution_code=inst_code)
    notify(db, kpt_reviewer_ids(db), "REGISTRATION_SUBMITTED", f"Permohonan akaun IPT baharu: {inst_name}",
           f"{name} ({account_email}) memohon akaun Penyelaras IPT. No. permohonan {app.ref_no}.", "#/kpt/permohonan")
    send_email(db, account_email, "PSKG Monitor 2030: Permohonan akaun diterima",
               f"Salam {name},\n\nPermohonan akaun anda bagi {inst_name} telah diterima dan sedang menunggu kelulusan "
               f"Penyelaras KPT.\n\nNo. permohonan: {app.ref_no}\nKod semakan: {status_code}\n\n"
               f"Semak status: {link('#/status')}\n", kind="REGISTRATION_SUBMITTED")
    db.commit()
    return {"message": "Permohonan akaun anda telah berjaya dihantar dan sedang menunggu kelulusan Penyelaras KPT.",
            "ref_no": app.ref_no, "status_code": status_code, "status": APP_STATUS_LABEL[APP_PENDING]}


class StatusCheckIn(BaseModel):
    ref_no: str = Field(max_length=40)
    status_code: str = Field(max_length=40)


@router.post("/register/status")
def registration_status(req: StatusCheckIn, request: Request, db: Session = Depends(get_db)):
    throttle(db, "status_check", client_ip(request), settings.public_form_limit * 2)
    app = db.scalar(select(RegistrationApplication).where(
        RegistrationApplication.ref_no == req.ref_no.strip().upper()))
    if not app or not app.status_code_digest or not secrets.compare_digest(
            app.status_code_digest, digest(req.status_code.strip().upper())):
        raise HTTPException(404, "Gabungan No. Permohonan dan Kod Semakan tidak ditemui.")
    return {"ref_no": app.ref_no, "status": app.status, "status_label": APP_STATUS_LABEL.get(app.status, app.status),
            "institution": app.inst_name, "submitted_at": app.submitted_at, "decided_at": app.decided_at,
            "reason": app.decision_reason if app.status == "REJECTED" else None}


# ------------------------------------------------------------------ activation & reset tokens
def _valid_token(db: Session, token: str, purpose: str) -> AccountInvitation:
    inv = db.scalar(select(AccountInvitation).where(AccountInvitation.token_digest == digest(token or "")))
    if not inv or inv.purpose != purpose:
        raise HTTPException(404, "Pautan tidak sah.")
    if inv.used_at:
        raise HTTPException(410, "Pautan ini telah digunakan.")
    if inv.revoked_at:
        raise HTTPException(410, "Pautan ini telah dibatalkan. Sila minta pautan baharu daripada Penyelaras KPT.")
    if aware(inv.expires_at) < utcnow():
        raise HTTPException(410, "Pautan ini telah tamat tempoh. Sila minta Penyelaras KPT menghantar semula jemputan.")
    return inv


class TokenIn(BaseModel):
    token: str = Field(max_length=200)


@router.post("/activation/details")
def activation_details(req: TokenIn, request: Request, db: Session = Depends(get_db)):
    throttle(db, "activation_view", client_ip(request), 60)
    inv = _valid_token(db, req.token, "ACTIVATION")
    u = db.get(User, inv.user_id)
    inst = db.get(Institution, inv.institution_id) if inv.institution_id else None
    return {"name": u.name, "email": u.email, "position": u.position, "department": u.department, "phone": u.phone,
            "institution": {"code": inst.code, "name": inst.name, "category": inst.category} if inst else None,
            "expires_at": inv.expires_at}


class ActivationIn(BaseModel):
    token: str = Field(max_length=200)
    confirm_details: bool
    password: str = Field(max_length=200)
    confirm_password: str = Field(max_length=200)


@router.post("/activation")
def activate(req: ActivationIn, request: Request, db: Session = Depends(get_db)):
    throttle(db, "activation", client_ip(request), settings.public_form_limit)
    inv = _valid_token(db, req.token, "ACTIVATION")
    if not req.confirm_details:
        raise HTTPException(422, "Sila sahkan bahawa maklumat anda adalah tepat.")
    u = db.get(User, inv.user_id)
    if u.status != USER_INVITED:
        raise HTTPException(409, "Akaun ini tidak lagi menunggu pengaktifan.")
    validate_password(req.password, req.confirm_password, u.email)
    u.password_digest = password_hash.hash(req.password)
    u.status = USER_ACTIVE
    u.activated_at = utcnow()
    u.password_changed_at = utcnow()
    inv.used_at = utcnow()
    db.add(AccountApproval(user_id=u.id, institution_id=u.institution_id, action="ACTIVATED", actor_id=u.id))
    audit(db, u, "account_activated", f"user:{u.id}", request)
    notify(db, [inv.created_by] if inv.created_by else kpt_reviewer_ids(db), "ACCOUNT_ACTIVATED",
           f"Akaun diaktifkan: {u.name}", f"{u.email} telah mengaktifkan akaun Penyelaras IPT.", "#/kpt/akaun")
    send_email(db, u.email, "PSKG Monitor 2030: Akaun diaktifkan",
               f"Salam {u.name},\n\nAkaun anda telah berjaya diaktifkan. Log masuk di {link('#/login')}.\n",
               kind="ACCOUNT_ACTIVATED")
    db.commit()
    return {"message": "Akaun anda telah diaktifkan. Sila log masuk."}


class ForgotIn(BaseModel):
    email: str = Field(max_length=200)


@router.post("/password/forgot")
def forgot_password(req: ForgotIn, request: Request, db: Session = Depends(get_db)):
    throttle(db, "forgot", client_ip(request), settings.public_form_limit)
    email = (req.email or "").strip().lower()
    u = db.scalar(select(User).where(User.email == email))
    if u and u.status == USER_ACTIVE:
        token = new_token()
        db.add(AccountInvitation(user_id=u.id, institution_id=u.institution_id, purpose="PASSWORD_RESET",
                                 token_digest=digest(token), created_by=None,
                                 expires_at=utcnow() + timedelta(hours=settings.reset_hours)))
        send_email(db, u.email, "PSKG Monitor 2030: Tetapan semula kata laluan",
                   f"Salam {u.name},\n\nGunakan pautan sekali guna ini dalam tempoh {settings.reset_hours} jam:\n"
                   f"{link('#/reset?token=' + token)}\n\nAbaikan emel ini jika anda tidak membuat permintaan.\n",
                   kind="PASSWORD_RESET")
        audit(db, u, "password_reset_requested", f"user:{u.id}", request)
    db.commit()
    # Identical response whether or not the account exists (no account enumeration).
    return {"message": "Jika emel tersebut berdaftar dan aktif, arahan tetapan semula telah dihantar."}


class ResetIn(BaseModel):
    token: str = Field(max_length=200)
    password: str = Field(max_length=200)
    confirm_password: str = Field(max_length=200)


@router.post("/password/reset")
def reset_password(req: ResetIn, request: Request, db: Session = Depends(get_db)):
    throttle(db, "reset", client_ip(request), settings.public_form_limit)
    inv = _valid_token(db, req.token, "PASSWORD_RESET")
    u = db.get(User, inv.user_id)
    validate_password(req.password, req.confirm_password, u.email)
    u.password_digest = password_hash.hash(req.password)
    u.password_changed_at = utcnow()
    inv.used_at = utcnow()
    revoke_user_sessions(db, u.id)
    audit(db, u, "password_reset", f"user:{u.id}", request)
    db.commit()
    return {"message": "Kata laluan telah ditetapkan semula. Sila log masuk."}
