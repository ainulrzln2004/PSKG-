"""Create the FIRST Pentadbir KPT (administrator) account. Run once; not needed on every start-up.

Run:  python -m scripts.bootstrap_admin
"""
import getpass
import sys

from sqlalchemy import select

from app.db import SessionLocal
from app.migrate import upgrade_to_head
from app.models import ROLE_ADMIN, USER_ACTIVE, AccountApproval, User, utcnow
from app.security import password_hash, password_problems


def main() -> None:
    upgrade_to_head()
    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.role == ROLE_ADMIN, User.status == USER_ACTIVE))
        if existing and "--another" not in sys.argv:
            print(f"Pentadbir KPT aktif sudah wujud ({existing.email}). Tiada tindakan diambil.")
            print("Gunakan menu Pentadbiran > Pengguna untuk menambah pengguna, atau jalankan dengan --another.")
            return
        email = input("Emel Pentadbir KPT: ").strip().lower()
        name = input("Nama penuh: ").strip()
        password = getpass.getpass("Kata laluan (min. 12 aksara, huruf besar, huruf kecil, nombor): ")
        confirm = getpass.getpass("Sahkan kata laluan: ")
        problems = password_problems(password, email)
        if "@" not in email or len(name) < 3:
            raise SystemExit("Emel atau nama tidak sah.")
        if password != confirm:
            raise SystemExit("Pengesahan kata laluan tidak sepadan.")
        if problems:
            raise SystemExit("Kata laluan mesti mempunyai " + ", ".join(problems) + ".")
        if db.scalar(select(User).where(User.email == email)):
            raise SystemExit("Emel telah wujud.")
        u = User(email=email, name=name, password_digest=password_hash.hash(password), role=ROLE_ADMIN,
                 status=USER_ACTIVE, activated_at=utcnow(), password_changed_at=utcnow())
        db.add(u)
        db.flush()
        db.add(AccountApproval(user_id=u.id, action="BOOTSTRAP_ADMIN", actor_id=None, reason="scripts.bootstrap_admin"))
        db.commit()
    print("Pentadbir KPT berjaya dicipta. Kata laluan tidak disimpan dalam projek.")


if __name__ == "__main__":
    main()
