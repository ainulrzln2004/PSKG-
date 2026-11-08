"""Cross-cutting services: audit logging, notifications, e-mail delivery and settings."""
from __future__ import annotations

import json
import logging
import smtplib
from email.message import EmailMessage
from typing import Iterable, Optional

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import DEFAULT_PILOT_NOTICE, settings
from .models import (ROLE_ADMIN, ROLE_KPT, USER_ACTIVE, AppSetting, Audit, EmailOutbox, Notification, User,
                     utcnow)
from .security import client_ip

log = logging.getLogger("pskg")


# ------------------------------------------------------------------ audit
def audit(db: Session, actor: Optional[User], event: str, record: str, request: Optional[Request] = None,
          **detail) -> None:
    db.add(Audit(actor_id=actor.id if actor else None, event=event, record=record[:250],
                 at=utcnow().replace(tzinfo=None), ip_address=client_ip(request)[:64] if request else None,
                 detail=json.dumps(detail, ensure_ascii=False, default=str) if detail else None))


# ------------------------------------------------------------------ settings
SETTING_DEFAULTS = {
    "pilot_notice_enabled": "true",
    "pilot_notice": DEFAULT_PILOT_NOTICE,
    "evidence_required_on_submit": "true",
    "default_reporting_year": "2026",
}


def get_setting(db: Session, key: str) -> str:
    row = db.get(AppSetting, key)
    return row.value if row else SETTING_DEFAULTS.get(key, "")


def setting_bool(db: Session, key: str) -> bool:
    return get_setting(db, key).strip().lower() in {"1", "true", "yes", "on"}


def set_setting(db: Session, key: str, value: str, actor: Optional[User]) -> None:
    row = db.get(AppSetting, key)
    if row is None:
        row = AppSetting(key=key, value=value)
        db.add(row)
    row.value = value
    row.updated_by = actor.id if actor else None
    row.updated_at = utcnow()


# ------------------------------------------------------------------ notifications
def notify(db: Session, user_ids: Iterable[int], kind: str, title: str, body: str = "",
           link: Optional[str] = None) -> None:
    for uid in set(user_ids):
        db.add(Notification(user_id=uid, kind=kind, title=title[:200], body=body, link=link))


def kpt_reviewer_ids(db: Session, need_verify: bool = False) -> list[int]:
    q = select(User).where(User.role.in_([ROLE_KPT, ROLE_ADMIN]), User.status == USER_ACTIVE)
    users = db.scalars(q).all()
    return [u.id for u in users if (u.can_verify or not need_verify)]


def institution_user_ids(db: Session, institution_id: int) -> list[int]:
    return list(db.scalars(select(User.id).where(User.institution_id == institution_id, User.status == USER_ACTIVE)))


def send_email(db: Session, to: str, subject: str, body: str, kind: str = "") -> EmailOutbox:
    """Send via SMTP when configured; otherwise keep a clearly-marked development preview.

    The system never claims delivery when SMTP is not configured.
    """
    row = EmailOutbox(to_email=to, subject=subject[:250], body=body, kind=kind, status="DEV_PREVIEW")
    db.add(row)
    if not settings.smtp_enabled:
        return row
    try:
        msg = EmailMessage()
        msg["From"] = settings.smtp_from
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            if settings.smtp_starttls:
                smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
        row.status = "SENT"
        row.sent_at = utcnow()
        # Do not retain single-use links once the e-mail has left the system.
        if "token=" in body:
            row.body = "\n".join("[pautan sekali guna disembunyikan selepas penghantaran]" if "token=" in ln else ln
                                 for ln in body.splitlines())
    except Exception as exc:  # pragma: no cover - depends on external SMTP
        log.warning("SMTP delivery failed: %s", exc)
        row.status = "FAILED"
        row.error = str(exc)[:500]
    return row


def link(path: str) -> str:
    return f"{settings.public_url}/{path.lstrip('/')}"
