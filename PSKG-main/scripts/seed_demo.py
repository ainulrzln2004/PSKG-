"""Create SYNTHETIC demonstration data (fictitious institutions, no personal data).

Run:  python -m scripts.seed_demo                 (asks for the demo password)
      python -m scripts.seed_demo --generate      (generates and prints a random demo password)

All demo institutions are flagged is_demo and named "(DEMO)". The workflow is executed through the
real HTTP API (registration, draft, evidence upload, submission, KPT verification), so revisions,
verification history, notifications and audit records are produced exactly as in normal use.
No existing administrator account is required: demo staff accounts are created by this script.
"""
from __future__ import annotations

import getpass
import secrets
import string
import sys

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.kpi_catalogue import KPI_CATALOGUE
from app.migrate import upgrade_to_head
from app.models import (ROLE_EXEC, ROLE_IPT, ROLE_KPT, USER_ACTIVE, Institution, KpiMilestone, User, utcnow)
from app.security import password_hash, password_problems

DEMO_PDF = (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
            b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 120]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj "
            b"4 0 obj<</Length 58>>stream\nBT /F1 14 Tf 20 60 Td (Bukti sintetik - DATA DEMO) Tj ET\nendstream endobj "
            b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n")

INSTITUTIONS = [  # code, name, category, state, enrolment, graduates, programmes, performance factor
    ("DEMO-UA1", "Universiti Demo Alpha (DEMO)", "UA", "Selangor", 25000, 6000, 120, 1.25),
    ("DEMO-UA2", "Universiti Demo Beta (DEMO)", "UA", "Pulau Pinang", 18000, 4200, 95, 0.85),
    ("DEMO-POLI1", "Politeknik Demo Gamma (DEMO)", "POLITEKNIK", "Perak", 9000, 3000, 40, 1.0),
    ("DEMO-IPTS1", "Kolej Universiti Demo Delta (DEMO)", "IPTS", "Johor", 6000, 1500, 30, 0.7),
]


def _password() -> str:
    if "--generate" in sys.argv:
        alphabet = string.ascii_letters + string.digits
        while True:
            pw = "Demo-" + "".join(secrets.choice(alphabet) for _ in range(14))
            if not password_problems(pw):
                return pw
    pw = getpass.getpass("Kata laluan untuk SEMUA akaun demo (min. 12 aksara, huruf besar/kecil, nombor): ")
    problems = password_problems(pw)
    if problems:
        raise SystemExit("Kata laluan mesti mempunyai " + ", ".join(problems) + ".")
    return pw


def _values(k: dict, enrol: int, grads: int, progs: int, factor: float, n: int) -> dict:
    t = k["targets"][0]["value"] or 1
    if k["unit"] == "count":
        if k["itemised"]:
            count = max(0, round(t * factor / 2))
            return {"items": [{"ref": f"DEMO-{k['code'].replace('/', '')}-{n}-{i}", "title": f"Item demo {i}",
                               "ip_type": "Paten", "college": "Kolej Kediaman Demo"} for i in range(1, count + 1)],
                    "numerator": count, "attestations": [True] * len(k["attestations"])}
        return {"numerator": max(0, round(t * factor / 3))}
    label = (k["denominator_label"] or "").lower()
    den = grads if "graduan" in label else progs if "program" in label else max(10, progs // 3) if "sulam" in label else enrol
    num = min(den, round(den * t * factor / 100))
    return {"numerator": num, "denominator": den, "attestations": [True] * len(k["attestations"])}


def main() -> None:
    upgrade_to_head()
    from app.main import app
    with SessionLocal() as db:
        if db.scalar(select(Institution).where(Institution.code == "DEMO-UA1")):
            print("Data demo sudah wujud. Tiada tindakan diambil.")
            return
    pw = _password()
    with SessionLocal() as db:
        def mk(email, name, role, inst=None):
            u = User(email=email, name=name, password_digest=password_hash.hash(pw), role=role, status=USER_ACTIVE,
                     institution_id=inst, activated_at=utcnow(), position="Pegawai (DEMO)", department="Data Demo")
            db.add(u)
            db.flush()
            return u
        kpt = mk("kpt.demo@pskg-demo.test", "Penyelaras KPT (DEMO)", ROLE_KPT)
        mk("eksekutif.demo@pskg-demo.test", "Pengurusan Tertinggi (DEMO)", ROLE_EXEC)
        ipt_emails = []
        for code, name, cat, state, *_ in INSTITUTIONS:
            inst = Institution(name=name, code=code, status="ACTIVE", category=cat, state=state, is_demo=True,
                               created_via="DEMO_SEED", official_email=f"info@{code.lower()}.pskg-demo.test",
                               address="Alamat demo")
            db.add(inst)
            db.flush()
            email = f"penyelaras@{code.lower()}.pskg-demo.test"
            mk(email, f"Penyelaras {code} (DEMO)", ROLE_IPT, inst.id)
            ipt_emails.append(email)
        kpi17 = next(k for k in KPI_CATALOGUE if k["code"] == "T4/OS2/B")
        db.add(KpiMilestone(kpi_id=kpi17["id"], year=2026, progress_pct=45, recorded_by=kpt.id,
                            note="DEMO: instrumen indeks dalam pembangunan (data sintetik)"))
        db.commit()

    H = {"X-Requested-With": "PSKG"}
    with TestClient(app, headers=H) as reviewer:
        reviewer.post("/api/login", json={"email": "kpt.demo@pskg-demo.test", "password": pw}).raise_for_status()
        for idx, ((code, _, cat, _, enrol, grads, progs, factor), email) in enumerate(zip(INSTITUTIONS, ipt_emails)):
            c = TestClient(app, headers=H)
            c.post("/api/login", json={"email": email, "password": pw}).raise_for_status()
            for n, k in enumerate(KPI_CATALOGUE):
                if k["unit"] == "index":
                    continue  # 2026 is a national milestone year for the Employer Satisfaction Index
                if code == "DEMO-IPTS1" and n > 4:
                    break  # Delta has only started a few drafts
                f = factor * (0.8 + ((n * 7 + idx * 3) % 9) / 10)
                r = c.put("/api/ipt/submissions", json={"kpi_id": k["id"], "year": 2026,
                                                        "note": "DATA SINTETIK UNTUK DEMONSTRASI",
                                                        **_values(k, enrol, grads, progs, f, idx)})
                r.raise_for_status()
                sid = r.json()["submission"]["id"]
                if code == "DEMO-IPTS1" or (code == "DEMO-POLI1" and n >= 15):
                    continue  # stays as draft
                c.post(f"/api/ipt/submissions/{sid}/evidence",
                       files={"file": (f"Bukti_{k['code'].replace('/', '-')}_DEMO.pdf", DEMO_PDF, "application/pdf")}).raise_for_status()
                c.post(f"/api/ipt/submissions/{sid}/submit").raise_for_status()
                if code == "DEMO-POLI1" and n >= 12:
                    continue  # awaiting review
                if code == "DEMO-UA2" and n in (3, 8):
                    reviewer.post(f"/api/submissions/{sid}/review",
                                  json={"decision": "RETURNED", "comment": "DEMO: sila sahkan skop penyebut."}).raise_for_status()
                    continue
                reviewer.post(f"/api/submissions/{sid}/review", json={"decision": "VERIFIED", "comment": "DEMO"}).raise_for_status()
        # A pending self-registration awaiting Penyelaras KPT approval
        pub = TestClient(app, headers=H)
        pub.post("/api/register", json=dict(
            existing_institution_id=None, inst_name="Kolej Komuniti Demo Epsilon (DEMO)", inst_code="DEMO-KK1",
            inst_category="KK", inst_address="Alamat demo", inst_state="Kedah", inst_email="info@demo-kk1.pskg-demo.test",
            coordinator_name="Pemohon Demo Epsilon", position="Penyelaras Kerjaya", department="Unit Kerjaya",
            official_email="pegawai@demo-kk1.pskg-demo.test", phone="04-7001234",
            account_email="penyelaras@demo-kk1.pskg-demo.test", password=pw, confirm_password=pw)).raise_for_status()

    print("\nData demo SINTETIK berjaya dicipta.")
    print("Akaun (kata laluan sama untuk semua):")
    print("  Penyelaras KPT       : kpt.demo@pskg-demo.test")
    print("  Pengurusan Tertinggi : eksekutif.demo@pskg-demo.test")
    for e in ipt_emails:
        print(f"  Penyelaras IPT       : {e}")
    print("  Permohonan menunggu  : penyelaras@demo-kk1.pskg-demo.test (belum boleh log masuk)")
    if "--generate" in sys.argv:
        print(f"\nKata laluan demo: {pw}\n(Simpan sekarang — ia tidak disimpan di mana-mana.)")


if __name__ == "__main__":
    main()
