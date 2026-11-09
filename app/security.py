"""Authentication, sessions, authorisation and throttling."""
from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from fastapi import Depends, HTTPException, Request
from pwdlib import PasswordHash
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import (ROLE_ADMIN, ROLE_EXEC, ROLE_IPT, ROLE_KPT, USER_ACTIVE, Institution, LoginAttempt,
                     LoginSession, RateEvent, User, utcnow)

password_hash = PasswordHash.recommended()
_DUMMY_HASH = password_hash.hash("timing-equaliser-not-a-password")
SESSION_COOKIE = "pskg_session"
CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "PSKG"


# ------------------------------------------------------------------ helpers
def aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def client_ip(request: Optional[Request]) -> str:
    if request is None or request.client is None:
        return "unknown"
    return request.client.host or "unknown"


EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+'-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def normalise_email(value: str) -> str:
    email = (value or "").strip().lower()
    if len(email) > 200 or not EMAIL_RE.match(email):
        raise HTTPException(422, "Format emel tidak sah.")
    return email


def password_problems(password: str, email: str = "") -> list[str]:
    problems = []
    if len(password) < 12:
        problems.append("sekurang-kurangnya 12 aksara")
    if len(password) > 128:
        problems.append("tidak melebihi 128 aksara")
    if not re.search(r"[a-z]", password):
        problems.append("sekurang-kurangnya satu huruf kecil")
    if not re.search(r"[A-Z]", password):
        problems.append("sekurang-kurangnya satu huruf besar")
    if not re.search(r"\d", password):
        problems.append("sekurang-kurangnya satu nombor")
    local = email.split("@")[0].lower() if email else ""
    if local and len(local) >= 4 and local in password.lower():
        problems.append("tidak mengandungi nama pengguna emel")
    if password.lower() in {"password1234", "katalaluan123", "123456789012", "qwertyuiop12"}:
        problems.append("tidak menggunakan kata laluan biasa")
    return problems


def validate_password(password: str, confirm: Optional[str] = None, email: str = "") -> None:
    if confirm is not None and password != confirm:
        raise HTTPException(422, "Pengesahan kata laluan tidak sepadan.")
    problems = password_problems(password, email)
    if problems:
        raise HTTPException(422, "Kata laluan mesti mempunyai " + ", ".join(problems) + ".")


def verify_password(password: str, stored: Optional[str]) -> bool:
    if not stored:
        password_hash.verify(password, _DUMMY_HASH)  # equalise timing
        return False
    try:
        return password_hash.verify(password, stored)
    except Exception:
        return False


# ------------------------------------------------------------------ throttling
def login_blocked(db: Session, email: str, ip: str) -> bool:
    since = utcnow() - timedelta(minutes=settings.login_window_minutes)
    by_email = db.scalar(select(func.count()).select_from(LoginAttempt).where(
        LoginAttempt.email == email, LoginAttempt.success.is_(False), LoginAttempt.at >= since)) or 0
    by_ip = db.scalar(select(func.count()).select_from(LoginAttempt).where(
        LoginAttempt.ip_address == ip, LoginAttempt.success.is_(False), LoginAttempt.at >= since)) or 0
    return by_email >= settings.login_max_failures or by_ip >= settings.ip_max_failures


def record_login_attempt(db: Session, email: str, ip: str, success: bool) -> None:
    db.add(LoginAttempt(email=email[:200], ip_address=ip[:64], success=success))
    if success:  # successful login clears the failure streak for this account
        db.execute(delete(LoginAttempt).where(LoginAttempt.email == email, LoginAttempt.success.is_(False)))


def throttle(db: Session, bucket: str, key: str, limit: int, window_minutes: int = 60) -> None:
    since = utcnow() - timedelta(minutes=window_minutes)
    count = db.scalar(select(func.count()).select_from(RateEvent).where(
        RateEvent.bucket == bucket, RateEvent.key == key, RateEvent.at >= since)) or 0
    if count >= limit:
        raise HTTPException(429, "Terlalu banyak cubaan. Sila cuba semula kemudian.")
    db.add(RateEvent(bucket=bucket, key=key[:200]))
    db.commit()


# ------------------------------------------------------------------ sessions
def create_session(db: Session, user: User, request: Optional[Request]) -> str:
    token = new_token(48)
    db.add(LoginSession(user_id=user.id, token_digest=digest(token),
                        expires_at=(utcnow() + timedelta(hours=settings.session_hours)).replace(tzinfo=None),
                        ip_address=client_ip(request)[:64],
                        user_agent=(request.headers.get("user-agent", "")[:300] if request else None)))
    # Opportunistic clean-up of expired sessions
    db.execute(delete(LoginSession).where(LoginSession.expires_at < utcnow().replace(tzinfo=None)))
    return token


def revoke_user_sessions(db: Session, user_id: int) -> None:
    db.execute(delete(LoginSession).where(LoginSession.user_id == user_id))


def _token_from_request(request: Request) -> Optional[str]:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return request.cookies.get(SESSION_COOKIE)


def account_block_reason(db: Session, user: User) -> Optional[str]:
    if user.status != USER_ACTIVE:
        return {
            "pending": "Akaun anda masih menunggu kelulusan Penyelaras KPT.",
            "invited": "Akaun anda belum diaktifkan. Sila gunakan pautan pengaktifan yang dihantar kepada anda.",
            "rejected": "Permohonan akaun anda telah ditolak. Sila hubungi Penyelaras KPT.",
            "inactive": "Akaun anda telah dinyahaktifkan. Sila hubungi Penyelaras KPT.",
        }.get(user.status, "Akaun tidak aktif.")
    if user.role == ROLE_IPT:
        inst = db.get(Institution, user.institution_id) if user.institution_id else None
        if not inst or inst.status != "ACTIVE":
            return "Institusi anda belum aktif atau telah dinyahaktifkan. Sila hubungi Penyelaras KPT."
    return None


def current_session(request: Request, db: Session = Depends(get_db)) -> LoginSession:
    token = _token_from_request(request)
    if not token:
        raise HTTPException(401, "Sila log masuk.")
    s = db.scalar(select(LoginSession).where(LoginSession.token_digest == digest(token)))
    if not s or aware(s.expires_at) < utcnow():
        raise HTTPException(401, "Sesi telah tamat. Sila log masuk semula.")
    return s


def current_user(s: LoginSession = Depends(current_session), db: Session = Depends(get_db)) -> User:
    user = db.get(User, s.user_id)
    if not user:
        raise HTTPException(401, "Sesi tidak sah.")
    reason = account_block_reason(db, user)
    if reason:
        raise HTTPException(403, reason)
    return user


# ------------------------------------------------------------------ authorisation
KPT_PERMS = {"accounts.review", "accounts.preregister", "accounts.manage", "submissions.view_all",
             "submissions.verify", "monitoring.view", "dashboard.executive", "reports.national", "notifications.outbox"}
PERMISSIONS: dict[str, set[str]] = {
    ROLE_IPT: {"ipt.report", "reports.institution"},
    ROLE_KPT: KPT_PERMS,
    ROLE_ADMIN: KPT_PERMS | {"admin.users", "admin.institutions", "admin.periods", "admin.kpis", "admin.audit",
                             "admin.settings", "admin.milestones", "submissions.reopen"},
    ROLE_EXEC: {"dashboard.executive", "reports.national"},
}


def has_perm(user: User, perm: str) -> bool:
    if perm == "submissions.verify" and not user.can_verify:
        return False
    return perm in PERMISSIONS.get(user.role, set())


def require(*perms: str) -> Callable:
    """Dependency: the user must hold at least one of the permissions."""
    def dep(user: User = Depends(current_user)) -> User:
        if not any(has_perm(user, p) for p in perms):
            raise HTTPException(403, "Anda tidak mempunyai kebenaran untuk tindakan ini.")
        return user
    return dep


def permissions_of(user: User) -> list[str]:
    return sorted(p for p in PERMISSIONS.get(user.role, set()) if has_perm(user, p))
