"""End-to-end demonstrations A–D from the master prompt (§22), executed through the HTTP API."""
import io

from conftest import (PASSWORD, kpi_id, login, new_client, registration_payload, save, submit_verified, upload, uid)
from openpyxl import load_workbook

from app import analytics as A
from app.db import SessionLocal


def test_scenario_a_self_registration(kpt):
    officer = new_client()
    assert officer.get("/").status_code == 200                                   # 1 login page served
    p = registration_payload(inst_name=f"Universiti Senario A {uid()}")         # 2-3 registration form
    r = officer.post("/api/register", json=p)                                     # 4 submit
    assert r.status_code == 201
    ref, code = r.json()["ref_no"], r.json()["status_code"]
    st = officer.post("/api/register/status", json={"ref_no": ref, "status_code": code}).json()
    assert st["status"] == "PENDING_APPROVAL"                                     # 5 pending
    assert officer.post("/api/login", json={"email": p["account_email"], "password": PASSWORD}).status_code == 403  # 6
    apps = kpt.get("/api/kpt/applications").json()                                # 7-8 KPT opens module
    app = next(a for a in apps if a["ref_no"] == ref)
    assert kpt.get(f"/api/kpt/applications/{app['id']}").status_code == 200       # 9 review
    assert kpt.post(f"/api/kpt/applications/{app['id']}/approve", json={}).json()["status"] == "APPROVED"
    me = login(officer, p["account_email"])                                       # 10-11 active + login
    assert me["role"] == "ipt"
    assert officer.post("/api/register/status", json={"ref_no": ref, "status_code": code}).json()["status_label"] == "Diluluskan"


def test_scenario_b_kpt_preregistration(kpt):
    body = dict(existing_institution_id=None, inst_name=f"Kolej Komuniti Senario B {uid()}", inst_code="KKB" + uid().upper(),
                inst_category="KK", inst_state="Kedah", name="Puan Senario B", email=f"senario.b.{uid()}@kk.test",
                position="Penyelaras Kerjaya", department="Unit Perhubungan Industri", phone="04-7001234")
    r = kpt.post("/api/kpt/preregister", json=body)                               # 1-6
    assert r.status_code == 201
    link = r.json()["dev_activation_link"]                                        # 4 activation instructions (dev preview)
    token = link.split("token=")[1]
    officer = new_client()
    assert officer.post("/api/activation/details", json={"token": token}).json()["institution"]["code"] == body["inst_code"]
    r = officer.post("/api/activation", json={"token": token, "confirm_details": True, "password": PASSWORD,
                                              "confirm_password": PASSWORD})      # 5 secure activation
    assert r.status_code == 200
    me = login(officer, body["email"])                                            # 6 login
    assert me["institution"]["category"] == "KK"
    hist = kpt.get("/api/kpt/history").json()
    assert {"PRE_REGISTERED", "ACTIVATED"} <= {h["action"] for h in hist if body["email"] in (h["user"] or "")}


def test_scenario_c_kpi_reporting(kpt, executive):
    from conftest import approved_ipt
    ipt = approved_ipt(kpt)
    ov = ipt.get("/api/ipt/overview?year=2026").json()                            # 1 Teras 1
    t1 = next(t for t in ov["teras"] if t["teras"] == 1)
    assert [k["code"] for k in t1["kpis"]][0] == "T1/OS1/A"
    form = ipt.get(f"/api/ipt/form/{kpi_id('T1/OS1/A')}?year=2026").json()        # 2 open KPI
    assert form["editable"] and form["kpi"]["targets"]["2026"]["value"] == 2
    r = save(ipt, "T1/OS1/A", numerator=450, denominator=10000)                   # 3-4
    s = r.json()["submission"]
    assert s["value"] == 4.5                                                      # 5 calculated
    assert s["target"]["value"] == 2 and s["comparison"]["gap"] == 2.5            # 6 compared
    assert upload(ipt, s["id"], "Senarai_CBGE_2026.pdf").status_code == 201       # 7 evidence
    assert ipt.post(f"/api/ipt/submissions/{s['id']}/submit").json()["submission"]["status"] == "SUBMITTED"  # 8
    assert kpt.post(f"/api/submissions/{s['id']}/review", json={"decision": "VERIFIED", "comment": "Bukti lengkap"}).status_code == 200  # 9
    d = executive.get(f"/api/analytics/national?year=2026&institution_id={ipt.institution_id}").json()     # 10
    row = next(x for x in d["kpis"] if x["code"] == "T1/OS1/A")
    assert row["value"] == 4.5 and row["achieved"] is True


def test_scenario_d_national_aggregation_and_export(kpt, executive):
    from conftest import approved_ipt
    a, b, c = approved_ipt(kpt, "UA"), approved_ipt(kpt, "UA"), approved_ipt(kpt, "POLITEKNIK")
    submit_verified(a, kpt, "T4/OS1/B", numerator=1200, denominator=10000)
    submit_verified(b, kpt, "T4/OS1/B", numerator=300, denominator=5000)
    submit_verified(c, kpt, "T4/OS1/B", numerator=900, denominator=3000)
    ids = [a.institution_id, b.institution_id, c.institution_id]
    with SessionLocal() as db:
        r = next(x for x in A.national(A.Context(db, ids), 2026) if x["code"] == "T4/OS1/B")
        assert round(r["value"], 4) == round(100 * 2400 / 18000, 4)                # pooled 13.33 %
        ua = next(x for x in A.national(A.Context(db, ids, "UA"), 2026) if x["code"] == "T4/OS1/B")
        assert round(ua["value"], 4) == round(100 * 1500 / 15000, 4)               # category filter → 10 %
    # filters through the executive API
    one = executive.get(f"/api/analytics/national?year=2026&teras=4&institution_id={c.institution_id}").json()
    assert {k["teras"] for k in one["kpis"]} == {4}
    assert next(k for k in one["kpis"] if k["code"] == "T4/OS1/B")["value"] == 30.0
    # exports
    for fmt, magic in (("csv", b"\xef\xbb\xbf"), ("xlsx", b"PK"), ("pdf", b"%PDF")):
        resp = executive.get(f"/api/reports/national_kpi?year=2026&format={fmt}")
        assert resp.status_code == 200 and resp.content.startswith(magic), fmt
        assert "attachment" in resp.headers["content-disposition"]
    wb = load_workbook(io.BytesIO(executive.get("/api/reports/target_vs_actual?year=2026&format=xlsx").content))
    ws = wb.active
    text = "\n".join(str(c.value) for row in ws.iter_rows() for c in row if c.value is not None)
    for needle in ("Tahun pelaporan", "Skop pelaporan", "Dijana pada", "Kod KPI", "Sasaran", "Pencapaian", "Jurang", "Status pengesahan"):
        assert needle in text
    assert "T4/OS1/B" in text
