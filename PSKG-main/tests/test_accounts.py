"""Account registration, approval, pre-registration, activation and isolation (prompt §21 'Account Registration')."""
import re
from datetime import timedelta

from conftest import (PASSWORD, approved_ipt, kpi_id, login, make_user, new_client, registration_payload, save, uid)

from app.db import SessionLocal
from app.models import AccountInvitation, EmailOutbox, RegistrationApplication, User


def _app_id(kpt, ref):
    return next(a["id"] for a in kpt.get("/api/kpt/applications?status=").json() if a["ref_no"] == ref)


def test_1_2_self_registration_is_pending(client, kpt):
    p = registration_payload()
    r = client.post("/api/register", json=p)
    assert r.status_code == 201
    body = r.json()
    assert body["message"] == ("Permohonan akaun anda telah berjaya dihantar dan sedang menunggu kelulusan Penyelaras KPT.")
    assert re.match(r"REG-\d{4}-[0-9A-F]{6}", body["ref_no"])
    with SessionLocal() as db:
        app = db.query(RegistrationApplication).filter_by(ref_no=body["ref_no"]).one()
        assert app.status == "PENDING_APPROVAL"
        user = db.get(User, app.user_id)
        assert user.status == "pending" and user.institution_id is None
        assert user.password_digest.startswith("$argon2") and PASSWORD not in user.password_digest
    # visible to Penyelaras KPT
    rows = kpt.get("/api/kpt/applications").json()
    assert any(a["ref_no"] == body["ref_no"] and a["status_label"] == "Menunggu Kelulusan" for a in rows)
    # status check requires ref + secret code
    ok = client.post("/api/register/status", json={"ref_no": body["ref_no"], "status_code": body["status_code"]})
    assert ok.status_code == 200 and ok.json()["status_label"] == "Menunggu Kelulusan"
    bad = client.post("/api/register/status", json={"ref_no": body["ref_no"], "status_code": "WRONG"})
    assert bad.status_code == 404


def test_3_login_denied_before_approval(client):
    p = registration_payload()
    client.post("/api/register", json=p)
    r = client.post("/api/login", json={"email": p["account_email"], "password": PASSWORD})
    assert r.status_code == 403 and "menunggu kelulusan" in r.json()["detail"]
    # Wrong password must not reveal the pending state
    r = client.post("/api/login", json={"email": p["account_email"], "password": "Salah-Kata-Laluan-1"})
    assert r.status_code == 401 and "tidak sah" in r.json()["detail"]
    assert client.get("/api/ipt/overview?year=2026").status_code == 401


def test_4_approval_activates_account(client, kpt):
    p = registration_payload()
    ref = client.post("/api/register", json=p).json()["ref_no"]
    aid = _app_id(kpt, ref)
    detail = kpt.get(f"/api/kpt/applications/{aid}").json()
    assert detail["coordinator"]["position"] == "Timbalan Pendaftar" and detail["checks"]
    r = kpt.post(f"/api/kpt/applications/{aid}/approve", json={})
    assert r.status_code == 200 and r.json()["status"] == "APPROVED"
    me = login(client, p["account_email"])
    assert me["role"] == "ipt" and me["institution"]["code"] == p["inst_code"]
    with SessionLocal() as db:
        a = db.get(RegistrationApplication, aid)
        assert a.decided_by == kpt.user["id"] and a.decided_at is not None
        assert db.query(EmailOutbox).filter_by(to_email=p["account_email"], kind="REGISTRATION_APPROVED").count() == 1
    # cannot be decided twice
    assert kpt.post(f"/api/kpt/applications/{aid}/reject", json={"reason": "terlambat"}).status_code == 409


def test_5_rejection_requires_reason_and_blocks_login(client, kpt):
    p = registration_payload()
    ref = client.post("/api/register", json=p).json()["ref_no"]
    aid = _app_id(kpt, ref)
    assert kpt.post(f"/api/kpt/applications/{aid}/reject", json={"reason": ""}).status_code == 422
    r = kpt.post(f"/api/kpt/applications/{aid}/reject", json={"reason": "Identiti pemohon tidak dapat disahkan"})
    assert r.status_code == 200 and r.json()["status"] == "REJECTED"
    r = client.post("/api/login", json={"email": p["account_email"], "password": PASSWORD})
    assert r.status_code == 403 and "ditolak" in r.json()["detail"]


def test_6_duplicate_registration_prevented(client, kpt):
    p = registration_payload()
    assert client.post("/api/register", json=p).status_code == 201
    # same e-mail
    assert client.post("/api/register", json=registration_payload(account_email=p["account_email"])).status_code == 409
    # same institution code while pending
    dup = registration_payload(inst_code=p["inst_code"])
    assert client.post("/api/register", json=dup).status_code == 409
    # after approval, a new-institution registration with the same code is refused (must select existing)
    aid = _app_id(kpt, next(a["ref_no"] for a in kpt.get("/api/kpt/applications").json() if a["inst_code"] == p["inst_code"]))
    kpt.post(f"/api/kpt/applications/{aid}/approve", json={})
    r = client.post("/api/register", json=registration_payload(inst_code=p["inst_code"]))
    assert r.status_code == 409 and "telah berdaftar" in r.json()["detail"]


def test_password_policy_and_validation(client):
    r = client.post("/api/register", json=registration_payload(password="pendek", confirm_password="pendek"))
    assert r.status_code == 422
    r = client.post("/api/register", json=registration_payload(confirm_password="Lain-Lain-2026x"))
    assert r.status_code == 422 and "tidak sepadan" in r.json()["detail"]
    r = client.post("/api/register", json=registration_payload(inst_category="XYZ"))
    assert r.status_code == 422


def test_register_with_existing_institution(client, kpt):
    first = approved_ipt(kpt)
    p = registration_payload(existing_institution_id=first.institution_id, inst_name="", inst_code="")
    r = client.post("/api/register", json=p)
    assert r.status_code == 201
    aid = _app_id(kpt, r.json()["ref_no"])
    detail = kpt.get(f"/api/kpt/applications/{aid}").json()
    assert any("Akaun Penyelaras IPT aktif sedia ada" in c for c in detail["checks"])
    kpt.post(f"/api/kpt/applications/{aid}/approve", json={})
    me = login(client, p["account_email"])
    assert me["institution"]["id"] == first.institution_id


def _invite(kpt, **over):
    body = dict(existing_institution_id=None, inst_name=f"Politeknik Ujian {uid()}", inst_code="P" + uid().upper(),
                inst_category="POLITEKNIK", inst_state="Perak", name="Pegawai Jemputan", email=f"jemput.{uid()}@poli.test",
                position="Pegawai Kerjaya", department="Unit Kerjaya", phone="05-1234567")
    body.update(over)
    r = kpt.post("/api/kpt/preregister", json=body)
    assert r.status_code == 201, r.text
    token = r.json()["dev_activation_link"].split("token=")[1]
    return body, r.json(), token


def test_7_8_preregistration_and_secure_activation(client, kpt):
    body, res, token = _invite(kpt)
    # invited user cannot log in yet and has no password
    with SessionLocal() as db:
        u = db.get(User, res["user_id"])
        assert u.status == "invited" and u.password_digest is None
        inv = db.query(AccountInvitation).filter_by(user_id=u.id).one()
        assert inv.token_digest != token and len(inv.token_digest) == 64  # only the hash is stored
        mail = db.query(EmailOutbox).filter_by(to_email=body["email"], kind="INVITATION").one()
        assert mail.status == "DEV_PREVIEW"  # never claims delivery without SMTP
    d = client.post("/api/activation/details", json={"token": token})
    assert d.status_code == 200 and d.json()["email"] == body["email"]
    # must confirm details and choose a strong password
    assert client.post("/api/activation", json={"token": token, "confirm_details": False, "password": PASSWORD,
                                                "confirm_password": PASSWORD}).status_code == 422
    r = client.post("/api/activation", json={"token": token, "confirm_details": True, "password": PASSWORD,
                                             "confirm_password": PASSWORD})
    assert r.status_code == 200
    me = login(client, body["email"])
    assert me["role"] == "ipt" and me["institution"]["code"] == body["inst_code"]
    # single use
    assert new_client().post("/api/activation/details", json={"token": token}).status_code == 410


def test_9_expired_invitation_rejected_and_reissue(kpt):
    body, res, token = _invite(kpt)
    with SessionLocal() as db:
        inv = db.query(AccountInvitation).filter_by(user_id=res["user_id"]).one()
        inv.expires_at = inv.expires_at - timedelta(days=30)
        db.commit()
    c = new_client()
    r = c.post("/api/activation", json={"token": token, "confirm_details": True, "password": PASSWORD, "confirm_password": PASSWORD})
    assert r.status_code == 410 and "tamat tempoh" in r.json()["detail"]
    r = kpt.post(f"/api/kpt/accounts/{res['user_id']}/reissue")
    assert r.status_code == 200
    new_token = r.json()["dev_activation_link"].split("token=")[1]
    assert c.post("/api/activation", json={"token": new_token, "confirm_details": True, "password": PASSWORD,
                                           "confirm_password": PASSWORD}).status_code == 200


def test_preregistration_duplicates(kpt):
    body, _, _ = _invite(kpt)
    r = kpt.post("/api/kpt/preregister", json={**body, "inst_code": "X" + uid(), "inst_name": "Lain " + uid()})
    assert r.status_code == 409  # e-mail already has an account
    r = kpt.post("/api/kpt/preregister", json={**body, "email": f"lain.{uid()}@poli.test"})
    assert r.status_code == 409  # institution already exists → must select existing


def test_10_institution_isolation(kpt):
    a = approved_ipt(kpt)
    b = approved_ipt(kpt)
    r = save(a, "T1/OS1/A", numerator=10, denominator=100)
    sid = r.json()["submission"]["id"]
    assert b.get(f"/api/submissions/{sid}").status_code == 404
    assert all(s["institution"]["id"] == b.institution_id for s in b.get("/api/submissions").json())
    assert b.post(f"/api/ipt/submissions/{sid}/submit").status_code == 404
    # IPT users cannot reach KPT endpoints
    assert b.get("/api/kpt/applications").status_code == 403
    assert b.get("/api/monitoring/matrix?year=2026").status_code == 403
    # the analytics scope of an IPT user is forced to its own institution
    nat = b.get("/api/analytics/national?year=2026").json()
    assert nat["scope"] == "institution" and nat["institutions_in_scope"] == 1


def test_unauthorised_users_cannot_approve(client, executive):
    p = registration_payload()
    ref = client.post("/api/register", json=p).json()["ref_no"]
    with SessionLocal() as db:
        aid = db.query(RegistrationApplication).filter_by(ref_no=ref).one().id
    assert executive.post(f"/api/kpt/applications/{aid}/approve", json={}).status_code == 403
    assert client.post(f"/api/kpt/applications/{aid}/approve", json={}).status_code == 401


def test_deactivation_blocks_login(kpt):
    ipt = approved_ipt(kpt)
    uid_ = ipt.get("/api/me").json()["id"]
    assert kpt.post(f"/api/kpt/accounts/{uid_}/deactivate", json={"reason": "Pegawai bertukar"}).status_code == 200
    assert ipt.get("/api/me").status_code == 401  # sessions revoked
    r = new_client().post("/api/login", json={"email": ipt.payload["account_email"], "password": PASSWORD})
    assert r.status_code == 403
    assert kpt.post(f"/api/kpt/accounts/{uid_}/reactivate", json={}).status_code == 200
    login(new_client(), ipt.payload["account_email"])


def test_password_reset_flow(kpt):
    ipt = approved_ipt(kpt)
    email = ipt.payload["account_email"]
    c = new_client()
    r1 = c.post("/api/password/forgot", json={"email": email})
    r2 = c.post("/api/password/forgot", json={"email": f"tiada.{uid()}@x.test"})
    assert r1.json() == r2.json()  # no account enumeration
    with SessionLocal() as db:
        body = db.query(EmailOutbox).filter_by(to_email=email, kind="PASSWORD_RESET").one().body
    token = body.split("token=")[1].split()[0]
    new_pw = "Kata-Laluan-Baharu-2027"
    assert c.post("/api/password/reset", json={"token": token, "password": new_pw, "confirm_password": new_pw}).status_code == 200
    login(new_client(), email, new_pw)
    assert c.post("/api/password/reset", json={"token": token, "password": new_pw, "confirm_password": new_pw}).status_code == 410


def test_legacy_reviewer_role_mapping():
    from app.security import PERMISSIONS
    assert "submissions.verify" in PERMISSIONS["kpt"] and "admin.users" not in PERMISSIONS["kpt"]
    assert PERMISSIONS["executive"] == {"dashboard.executive", "reports.national"}
