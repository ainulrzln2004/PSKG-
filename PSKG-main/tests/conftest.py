"""Shared fixtures. Tests run against a throw-away SQLite database and storage folder."""
import os
import sys
import tempfile
import uuid
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="pskg_test_"))
# Set TEST_DATABASE_URL (e.g. an EMPTY PostgreSQL database) to run the suite against another engine.
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["STORAGE_DIR"] = str(_TMP / "storage")
os.environ["APP_ENV"] = "test"
os.environ["SMTP_HOST"] = ""
os.environ["LOGIN_IP_MAX_FAILURES"] = "100000"
os.environ["PUBLIC_FORM_LIMIT_PER_HOUR"] = "100000"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (ROLE_ADMIN, ROLE_EXEC, ROLE_KPT, USER_ACTIVE, Institution, ReportingPeriod, User,  # noqa: E402
                        utcnow)
from app.security import password_hash  # noqa: E402

PASSWORD = "Ujian-Kata-Laluan-2026"
PDF_BYTES = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"

with TestClient(app):  # run migrations once
    pass


def uid() -> str:
    return uuid.uuid4().hex[:8]


def new_client() -> TestClient:
    return TestClient(app, headers={"X-Requested-With": "PSKG"})


@pytest.fixture
def client():
    return new_client()


def make_user(role: str, **kw) -> dict:
    email = kw.pop("email", f"{role}.{uid()}@kpt.test")
    with SessionLocal() as db:
        u = User(email=email, name=kw.pop("name", f"Pegawai {role} {uid()}"), password_digest=password_hash.hash(PASSWORD),
                 role=role, status=USER_ACTIVE, activated_at=utcnow(), **kw)
        db.add(u)
        db.commit()
        return {"id": u.id, "email": email, "password": PASSWORD}


def login(c: TestClient, email: str, password: str = PASSWORD):
    r = c.post("/api/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["user"]


@pytest.fixture
def kpt():
    u = make_user(ROLE_KPT)
    c = new_client()
    login(c, u["email"])
    c.user = u
    return c


@pytest.fixture
def admin():
    u = make_user(ROLE_ADMIN)
    c = new_client()
    login(c, u["email"])
    c.user = u
    return c


@pytest.fixture
def executive():
    u = make_user(ROLE_EXEC)
    c = new_client()
    login(c, u["email"])
    c.user = u
    return c


def registration_payload(**over) -> dict:
    code = "T" + uid().upper()
    p = dict(existing_institution_id=None, inst_name=f"Universiti Ujian {code}", inst_code=code, inst_category="UA",
             inst_address="Jalan Ujian 1, 40450 Shah Alam", inst_state="Selangor", inst_email=f"info@{code.lower()}.edu.my",
             coordinator_name="Pegawai Ujian Satu", position="Timbalan Pendaftar", department="Pusat Kerjaya",
             official_email=f"pegawai@{code.lower()}.edu.my", phone="03-5544 2000",
             account_email=f"penyelaras.{code.lower()}@{code.lower()}.edu.my", password=PASSWORD, confirm_password=PASSWORD)
    p.update(over)
    return p


def approved_ipt(kpt_client: TestClient, category: str = "UA") -> TestClient:
    """Self-register an IPT, approve it as Penyelaras KPT, return a logged-in IPT client."""
    c = new_client()
    p = registration_payload(inst_category=category)
    r = c.post("/api/register", json=p)
    assert r.status_code == 201, r.text
    app_id = next(a["id"] for a in kpt_client.get("/api/kpt/applications").json() if a["ref_no"] == r.json()["ref_no"])
    assert kpt_client.post(f"/api/kpt/applications/{app_id}/approve", json={}).status_code == 200
    login(c, p["account_email"])
    me = c.get("/api/me").json()
    c.institution_id = me["institution"]["id"]
    c.payload = p
    return c


def kpi_id(code: str) -> int:
    from app.kpi_catalogue import KPI_BY_CODE
    return KPI_BY_CODE[code]["id"]


def save(c: TestClient, code: str, year: int = 2026, **values):
    return c.put("/api/ipt/submissions", json={"kpi_id": kpi_id(code), "year": year, **values})


def upload(c: TestClient, sid: int, name: str = "bukti.pdf", data: bytes = PDF_BYTES, ctype: str = "application/pdf"):
    return c.post(f"/api/ipt/submissions/{sid}/evidence", files={"file": (name, data, ctype)})


def submit_verified(ipt: TestClient, reviewer: TestClient, code: str, year: int = 2026, **values) -> int:
    r = save(ipt, code, year, **values)
    assert r.status_code == 200, r.text
    sid = r.json()["submission"]["id"]
    assert upload(ipt, sid).status_code == 201
    r = ipt.post(f"/api/ipt/submissions/{sid}/submit")
    assert r.status_code == 200, r.text
    r = reviewer.post(f"/api/submissions/{sid}/review", json={"decision": "VERIFIED", "comment": "Disemak"})
    assert r.status_code == 200, r.text
    return sid


def open_period(year: int) -> None:
    with SessionLocal() as db:
        p = db.query(ReportingPeriod).filter_by(year=year).one()
        p.status = "OPEN"
        db.commit()


def set_category(institution_id: int, category: str) -> None:
    with SessionLocal() as db:
        db.get(Institution, institution_id).category = category
        db.commit()
