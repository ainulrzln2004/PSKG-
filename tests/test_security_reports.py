"""Security controls, reports authorisation, admin controls and the configurable pilot notice."""
from conftest import (PASSWORD, ROLE_KPT, approved_ipt, make_user, new_client, save, submit_verified, uid)
from fastapi.testclient import TestClient

from app.main import app


def test_csrf_header_required_for_state_changes():
    raw = TestClient(app)  # no X-Requested-With header
    r = raw.post("/api/login", json={"email": "a@b.test", "password": "x"})
    assert r.status_code == 403 and "CSRF" in r.json()["detail"]


def test_security_headers_and_cookie(client):
    r = client.get("/")
    assert "script-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"
    u = make_user(ROLE_KPT)
    r = client.post("/api/login", json={"email": u["email"], "password": PASSWORD})
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    assert "token" not in r.json()  # session token is never exposed to JavaScript


def test_login_rate_limiting():
    u = make_user(ROLE_KPT)
    c = new_client()
    for _ in range(5):
        assert c.post("/api/login", json={"email": u["email"], "password": "Salah-Salah-123"}).status_code == 401
    r = c.post("/api/login", json={"email": u["email"], "password": PASSWORD})
    assert r.status_code == 429  # locked even with the right password during the window


def test_public_form_throttle(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "public_form_limit", 2)
    c = new_client()
    codes = [c.post("/api/register/status", json={"ref_no": "REG-X", "status_code": "Y"}).status_code for _ in range(6)]
    assert 429 in codes


def test_logout_revokes_session(kpt):
    assert kpt.get("/api/me").status_code == 200
    assert kpt.post("/api/logout").status_code == 200
    assert kpt.get("/api/me").status_code == 401


def test_static_spa_assets_served(client):
    for p in ("/static/js/core.js", "/static/css/app.css", "/static/vendor/chart.umd.js", "/static/vendor/bootstrap.min.css"):
        r = client.get(p)
        assert r.status_code == 200, p
    assert "javascript" in client.get("/static/js/app.js").headers["content-type"]


def test_report_authorisation(kpt, executive):
    ipt = approved_ipt(kpt)
    submit_verified(ipt, kpt, "T1/OS1/A", numerator=10, denominator=100)
    r = ipt.get("/api/reports/ipt_performance?year=2026&format=csv")
    assert r.status_code == 200
    body = r.content.decode("utf-8-sig")
    assert ipt.payload["inst_code"] in body and "Disahkan" in body
    assert ipt.get("/api/reports/reporting_status?year=2026&format=csv").status_code == 403
    assert executive.get("/api/reports/verification?year=2026&format=csv").status_code == 403
    assert executive.get("/api/reports/ipt_performance?year=2026&format=csv").status_code == 403
    for rep in ("reporting_status", "verification", "annual_trend", "by_teras", "ipt_performance"):
        for fmt in ("csv", "xlsx", "pdf"):
            assert kpt.get(f"/api/reports/{rep}?year=2026&format={fmt}").status_code == 200, (rep, fmt)


def test_pilot_notice_configurable(admin, client):
    assert client.get("/api/public/config").json()["pilot_notice"].startswith("PERSEKITARAN PILOT")
    r = admin.put("/api/admin/settings", json={"pilot_notice": "Sistem diluluskan KPT untuk operasi.", "pilot_notice_enabled": False})
    assert r.status_code == 200
    cfg = client.get("/api/public/config").json()
    assert cfg["pilot_notice"] == "Sistem diluluskan KPT untuk operasi." and cfg["pilot_notice_enabled"] is False
    admin.put("/api/admin/settings", json={"pilot_notice_enabled": True, "pilot_notice": (
        "PERSEKITARAN PILOT: Sasaran KPI merujuk jadual PSKG akhir; formula dan takrif pembilang/penyebut yang belum "
        "diperakukan masih dalam semakan. Dashboard hanya memaparkan data diluluskan. Jangan masukkan data peribadi "
        "graduan atau data rasmi tanpa kebenaran KPT.")})


def test_admin_target_change_requires_reason_and_is_audited(admin, kpt):
    from conftest import kpi_id
    k = kpi_id("T5/OS1/C")
    assert admin.put(f"/api/admin/kpis/{k}/targets", json={"year": 2030, "value": 800, "reason": ""}).status_code == 422
    assert kpt.put(f"/api/admin/kpis/{k}/targets", json={"year": 2030, "value": 800, "reason": "x" * 20}).status_code == 403
    assert admin.put(f"/api/admin/kpis/{k}/targets", json={"year": 2030, "value": 800, "reason": "Ujian perubahan terkawal"}).status_code == 200
    assert any(a["event"] == "target_changed" for a in admin.get("/api/admin/audit").json())
    admin.put(f"/api/admin/kpis/{k}/targets", json={"year": 2030, "value": 700, "reason": "Pulihkan nilai rasmi slaid 30"})


def test_admin_staff_invitation_and_last_admin_protection(admin):
    r = admin.post("/api/admin/users", json={"name": "Eksekutif Baharu", "email": f"exe.{uid()}@kpt.test", "role": "executive"})
    assert r.status_code == 201 and r.json()["dev_activation_link"]
    assert admin.post("/api/admin/users", json={"name": "IPT", "email": f"x.{uid()}@kpt.test", "role": "ipt"}).status_code == 422
    me = admin.get("/api/me").json()["id"]
    assert admin.patch(f"/api/admin/users/{me}", json={"status": "inactive", "reason": "ujian kendiri"}).status_code == 409


def test_period_management(admin, kpt):
    ipt = approved_ipt(kpt)
    assert admin.put("/api/admin/periods/2026", json={"status": "CLOSED"}).status_code == 200
    assert save(ipt, "T1/OS1/A", numerator=1, denominator=2).status_code == 409
    assert admin.put("/api/admin/periods/2026", json={"status": "OPEN"}).status_code == 200
    assert save(ipt, "T1/OS1/A", numerator=1, denominator=2).status_code == 200
