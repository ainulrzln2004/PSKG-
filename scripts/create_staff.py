"""Create a KPT staff account directly from the command line (alternative to the admin UI invitation).

Run:  python -m scripts.create_staff
Roles: kpt (Penyelaras KPT), executive (Pengurusan Tertinggi), admin (Pentadbir KPT).
Legacy V2B names 'reviewer' and 'viewer' are accepted and mapped to kpt / executive.
"""
import getpass

from sqlalchemy import select

from app.db import SessionLocal
from app.migrate import upgrade_to_head
from app.models import ROLE_ADMIN, ROLE_EXEC, ROLE_KPT, USER_ACTIVE, AccountApproval, User, utcnow
from app.security import password_hash, password_problems

ALIASES = {"reviewer": ROLE_KPT, "viewer": ROLE_EXEC, ROLE_KPT: ROLE_KPT, ROLE_EXEC: ROLE_EXEC, ROLE_ADMIN: ROLE_ADMIN}


def main() -> None:
    upgrade_to_head()
    role = ALIASES.get(input("Peranan (kpt/executive/admin): ").strip().lower())
    if not role:
        raise SystemExit("Peranan tidak sah.")
    email = input("Emel: ").strip().lower()
    name = input("Nama penuh: ").strip()
    pw = getpass.getpass("Kata laluan: ")
    if pw != getpass.getpass("Sahkan kata laluan: "):
        raise SystemExit("Pengesahan kata laluan tidak sepadan.")
    problems = password_problems(pw, email)
    if not name or "@" not in email or problems:
        raise SystemExit("Maklumat tidak sah. " + (("Kata laluan mesti mempunyai " + ", ".join(problems)) if problems else ""))
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)):
            raise SystemExit("Emel telah wujud.")
        u = User(email=email, name=name, password_digest=password_hash.hash(pw), role=role, status=USER_ACTIVE,
                 activated_at=utcnow(), password_changed_at=utcnow())
        db.add(u)
        db.flush()
        db.add(AccountApproval(user_id=u.id, action="STAFF_CREATED_CLI", reason=role))
        db.commit()
    print("Akaun staf dicipta.")


if __name__ == "__main__":
    main()
