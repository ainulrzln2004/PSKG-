"""KPT verification workflow (prompt §21 'KPT Verification')."""
from conftest import ROLE_KPT, approved_ipt, login, make_user, new_client, save, upload

from app.db import SessionLocal
from app.models import Notification, VerificationRecord


def _submitted(kpt, code="T1/OS1/A", **values):
    ipt = approved_ipt(kpt)
    sid = save(ipt, code, **(values or {"numerator": 300, "denominator": 6000})).json()["submission"]["id"]
    upload(ipt, sid)
    assert ipt.post(f"/api/ipt/submissions/{sid}/submit").status_code == 200
    return ipt, sid


def test_1_pending_submissions_appear_for_review(kpt):
    _, sid = _submitted(kpt)
    rows = kpt.get("/api/submissions?status=SUBMITTED&year=2026").json()
    assert any(r["id"] == sid for r in rows)
    with SessionLocal() as db:
        assert db.query(Notification).filter_by(user_id=kpt.user["id"], kind="REPORT_SUBMITTED").count() >= 1


def test_2_kpt_can_verify(kpt):
    ipt, sid = _submitted(kpt)
    detail = kpt.get(f"/api/submissions/{sid}").json()
    assert detail["can_review"] and detail["evidence"] and detail["kpi_full"]["numerator_label"]
    r = kpt.post(f"/api/submissions/{sid}/review", json={"decision": "VERIFIED", "comment": ""})
    assert r.status_code == 200 and r.json()["status"] == "VERIFIED"
    s = ipt.get(f"/api/submissions/{sid}").json()
    assert s["status"] == "VERIFIED" and s["reviewed_by"]
    # verified record cannot be silently edited
    assert save(ipt, "T1/OS1/A", numerator=1, denominator=2).status_code == 409
    assert kpt.post(f"/api/submissions/{sid}/review", json={"decision": "RETURNED", "comment": "ubah"}).status_code == 409


def test_3_kpt_can_return_with_mandatory_comment(kpt):
    ipt, sid = _submitted(kpt)
    assert kpt.post(f"/api/submissions/{sid}/review", json={"decision": "RETURNED", "comment": ""}).status_code == 422
    r = kpt.post(f"/api/submissions/{sid}/review", json={"decision": "RETURNED", "comment": "Lampirkan senarai pelajar agregat"})
    assert r.status_code == 200
    with SessionLocal() as db:
        n = db.query(Notification).filter_by(kind="REPORT_RETURNED").filter(Notification.user_id == ipt.get("/api/me").json()["id"]).one()
        assert "Lampirkan" in n.body


def test_4_returned_reports_can_be_corrected(kpt):
    ipt, sid = _submitted(kpt)
    kpt.post(f"/api/submissions/{sid}/review", json={"decision": "RETURNED", "comment": "Semak penyebut"})
    save(ipt, "T1/OS1/A", numerator=300, denominator=5000)
    assert ipt.post(f"/api/ipt/submissions/{sid}/submit").status_code == 200
    assert kpt.post(f"/api/submissions/{sid}/review", json={"decision": "VERIFIED"}).status_code == 200
    assert ipt.get(f"/api/submissions/{sid}").json()["value"] == 6.0


def test_5_verification_history_preserved(kpt):
    ipt, sid = _submitted(kpt)
    kpt.post(f"/api/submissions/{sid}/review", json={"decision": "RETURNED", "comment": "Pembetulan 1"})
    save(ipt, "T1/OS1/A", numerator=320, denominator=6000)
    ipt.post(f"/api/ipt/submissions/{sid}/submit")
    kpt.post(f"/api/submissions/{sid}/review", json={"decision": "VERIFIED", "comment": "OK"})
    h = kpt.get(f"/api/submissions/{sid}").json()["verification_history"]
    assert [x["decision"] for x in h] == ["RETURNED", "VERIFIED"]
    assert [x["revision"] for x in h] == [1, 2] and all(x["reviewer"] and x["at"] for x in h)
    assert h[0]["value"] == 5.0


def test_6_unauthorised_users_cannot_verify(kpt, executive):
    ipt, sid = _submitted(kpt)
    assert ipt.post(f"/api/submissions/{sid}/review", json={"decision": "VERIFIED"}).status_code == 403
    assert executive.post(f"/api/submissions/{sid}/review", json={"decision": "VERIFIED"}).status_code == 403
    assert new_client().post(f"/api/submissions/{sid}/review", json={"decision": "VERIFIED"}).status_code == 401
    # a Penyelaras KPT without verification authority
    u = make_user(ROLE_KPT, can_verify=False)
    c = new_client()
    login(c, u["email"])
    assert c.post(f"/api/submissions/{sid}/review", json={"decision": "VERIFIED"}).status_code == 403
    with SessionLocal() as db:
        assert db.query(VerificationRecord).filter_by(submission_id=sid).count() == 0


def test_admin_reopen_is_audited(kpt, admin):
    ipt, sid = _submitted(kpt)
    kpt.post(f"/api/submissions/{sid}/review", json={"decision": "VERIFIED"})
    assert kpt.post(f"/api/submissions/{sid}/reopen", json={"comment": "Ralat data dikesan oleh audit dalaman"}).status_code == 403
    assert admin.post(f"/api/submissions/{sid}/reopen", json={"comment": "pendek"}).status_code == 422
    assert admin.post(f"/api/submissions/{sid}/reopen", json={"comment": "Ralat data dikesan oleh audit dalaman"}).status_code == 200
    assert ipt.get(f"/api/submissions/{sid}").json()["status"] == "RETURNED"
    audit = admin.get("/api/admin/audit?event=submission_reopened").json()
    assert any(a["record"] == f"submission:{sid}" for a in audit)
