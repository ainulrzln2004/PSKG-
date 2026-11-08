"""KPI catalogue, calculations, validation, drafts, submissions, evidence (prompt §21 'KPI Reporting')."""
import json

import pytest
from conftest import PDF_BYTES, approved_ipt, kpi_id, open_period, save, set_category, submit_verified, upload

from app.db import SessionLocal
from app.models import SubmissionRevision

OFFICIAL = {  # slides 14, 18, 22, 26, 30
    "T1/OS1/A": [2, 4, 6, 8, 10], "T1/OS2/A": [5, 10, 15, 20, 25], "T1/OS2/B": [2, 4, 6, 8, 10],
    "T1/OS3/A": [2, 4, 6, 8, 10], "T1/OS3/B": [2, 4, 6, 8, 10], "T2/OS1/A": [20, 40, 60, 80, 100],
    "T2/OS1/B": [32, 34, 36, 38, 40], "T2/OS2/A": [2, 4, 6, 8, 10], "T2/OS2/B": [10, 12, 14, 16, 18],
    "T3/OS1/A": [5, 5, 5, 5, 5], "T3/OS1/B": [0.2, 0.4, 0.6, 0.8, 1], "T3/OS2/A": [2, 3, 4, 5, 6],
    "T3/OS2/B": [0.2, 0.4, 0.6, 0.8, 1], "T4/OS1/A": [1, 2, 3, 4, 5], "T4/OS1/B": [10, 20, 30, 40, 50],
    "T4/OS2/A": [20, 30, 40, 50, 60], "T4/OS2/B": [50, 100, 60, 70, 75], "T5/OS1/A": [2, 4, 6, 8, 10],
    "T5/OS1/B": [5, 15, 30, 45, 60], "T5/OS1/C": [300, 400, 500, 600, 700],
}


def test_1_all_20_kpis_load(kpt):
    kpis = kpt.get("/api/kpis").json()
    assert len(kpis) == 20
    assert [sum(1 for k in kpis if k["teras"] == t) for t in range(1, 6)] == [5, 4, 4, 4, 3]
    assert {k["code"] for k in kpis} == set(OFFICIAL)
    assert len({k["os_code"] for k in kpis}) == 10
    for k in kpis:
        assert k["formula_status"] == "draft" and k["numerator_label"] and k["data_owner"]
        if k["unit"] == "percent":
            assert k["denominator_label"]
    cbge = next(k for k in kpis if k["code"] == "T1/OS1/A")
    assert cbge["numerator_label"] == "Bilangan Pelajar Mengikut CBGE" and cbge["denominator_label"] == "Jumlah Enrolmen Pelajar"


def test_2_targets_2026_2030(kpt):
    for k in kpt.get("/api/kpis").json():
        assert [k["targets"][str(y)]["value"] for y in range(2026, 2031)] == OFFICIAL[k["code"]], k["code"]
    esi = next(k for k in kpt.get("/api/kpis").json() if k["code"] == "T4/OS2/B")
    assert [esi["targets"][str(y)]["kind"] for y in range(2026, 2031)] == ["milestone", "milestone", "value", "value", "value"]
    ip = next(k for k in kpt.get("/api/kpis").json() if k["code"] == "T3/OS1/A")
    assert ip["cumulative_target"] == 25


def test_3_percentage_calculation(kpt):
    ipt = approved_ipt(kpt)
    r = save(ipt, "T1/OS1/A", numerator=450, denominator=10000)
    s = r.json()["submission"]
    assert s["value"] == 4.5 and s["comparison"]["gap"] == 2.5 and s["comparison"]["achieved"] is True


def test_4_count_calculation(kpt):
    ipt = approved_ipt(kpt)
    s = save(ipt, "T5/OS1/C", numerator=320).json()["submission"]
    assert s["value"] == 320
    # national count targets are never imposed as an institutional quota
    assert s["comparison"]["achieved"] is None and "bukan kuota" in s["comparison"]["comparison"]
    # itemised count is derived from the list
    items = [{"ref": "MY-PI2026-001", "title": "Alat A", "ip_type": "Paten"}, {"ref": "MY-PI2026-002", "title": "Alat B", "ip_type": "Paten"}]
    s = save(ipt, "T3/OS1/A", numerator=99, items=items, attestations=[True]).json()["submission"]
    assert s["value"] == 2


@pytest.mark.parametrize("values,msg", [
    ({"numerator": -1, "denominator": 10}, "negatif"),
    ({"numerator": 1, "denominator": 0}, "sifar"),
    ({"numerator": 11, "denominator": 10}, "melebihi"),
    ({"numerator": 1.5, "denominator": 10}, "bulat"),
    ({"numerator": "abc", "denominator": 10}, "nombor"),
])
def test_5_invalid_numerator_denominator(kpt, values, msg):
    ipt = approved_ipt(kpt)
    r = save(ipt, "T1/OS2/A", **values)
    assert r.status_code == 422 and msg in r.json()["detail"]


def test_count_must_be_integer(kpt):
    ipt = approved_ipt(kpt)
    assert save(ipt, "T5/OS1/C", numerator=2.5).status_code == 422
    assert save(ipt, "T5/OS1/C", numerator=-3).status_code == 422


def test_non_subset_ratio_warns_not_blocks(kpt):
    ipt = approved_ipt(kpt)
    r = save(ipt, "T3/OS2/A", numerator=120, denominator=100)  # graduates ÷ enrolment per slide 22
    assert r.status_code == 200 and r.json()["warnings"]


def test_6_kpi17_special_handling(kpt):
    ua = approved_ipt(kpt, "UA")
    poli = approved_ipt(kpt, "POLITEKNIK")
    # 2026/2027 are national milestone years -> not reportable by IPT
    r = save(ua, "T4/OS2/B", 2026, index_score=4.2)
    assert r.status_code == 409 and "milestone" in r.json()["detail"].lower()
    form = ua.get(f"/api/ipt/form/{kpi_id('T4/OS2/B')}?year=2026").json()
    assert form["applicable"] is False
    open_period(2028)
    r = save(ua, "T4/OS2/B", 2028, index_score=4.2)
    assert r.status_code == 200
    s = r.json()["submission"]
    assert s["index_excellent"] is True and s["comparison"]["achieved"] is True
    assert save(ua, "T4/OS2/B", 2028, index_score=6).status_code == 422  # outside 1–5 scale
    r = save(ua, "T4/OS2/B", 2028, index_score=3.6)
    assert r.json()["submission"]["index_excellent"] is False
    # only IPTA (Universiti Awam) report the index
    assert save(poli, "T4/OS2/B", 2028, index_score=4.5).status_code == 409


def test_7_draft_allows_incomplete_and_8_submission_requires_complete(kpt):
    ipt = approved_ipt(kpt)
    r = save(ipt, "T1/OS3/A", numerator=50)
    assert r.status_code == 200 and r.json()["complete"] is False and r.json()["submission"]["status"] == "DRAFT"
    sid = r.json()["submission"]["id"]
    upload(ipt, sid)
    r = ipt.post(f"/api/ipt/submissions/{sid}/submit")
    assert r.status_code == 422 and "wajib" in r.json()["detail"]
    save(ipt, "T1/OS3/A", numerator=50, denominator=1000, note="Data Sistem Akademik, 31 Dis 2026")
    r = ipt.post(f"/api/ipt/submissions/{sid}/submit")
    assert r.status_code == 200 and r.json()["submission"]["status"] == "SUBMITTED"
    assert r.json()["submission"]["revision"] == 1
    # protected while submitted
    assert save(ipt, "T1/OS3/A", numerator=1, denominator=2).status_code == 409
    assert upload(ipt, sid).status_code == 409


def test_attestation_required_for_eligibility(kpt):
    ipt = approved_ipt(kpt)
    sid = save(ipt, "T2/OS1/A", numerator=5, denominator=20).json()["submission"]["id"]
    upload(ipt, sid)
    r = ipt.post(f"/api/ipt/submissions/{sid}/submit")
    assert r.status_code == 422 and "kelayakan" in r.json()["detail"]
    save(ipt, "T2/OS1/A", numerator=5, denominator=20, attestations=[True])
    assert ipt.post(f"/api/ipt/submissions/{sid}/submit").status_code == 200


def test_evidence_required_on_submit(kpt):
    ipt = approved_ipt(kpt)
    sid = save(ipt, "T1/OS2/B", numerator=3, denominator=60).json()["submission"]["id"]
    r = ipt.post(f"/api/ipt/submissions/{sid}/submit")
    assert r.status_code == 422 and "dokumen sokongan" in r.json()["detail"]


def test_9_correction_and_resubmission(kpt):
    ipt = approved_ipt(kpt)
    sid = save(ipt, "T4/OS1/B", numerator=900, denominator=10000).json()["submission"]["id"]
    upload(ipt, sid)
    ipt.post(f"/api/ipt/submissions/{sid}/submit")
    assert kpt.post(f"/api/submissions/{sid}/review", json={"decision": "RETURNED", "comment": "Penyebut tidak sepadan"}).status_code == 200
    form = ipt.get(f"/api/ipt/form/{kpi_id('T4/OS1/B')}?year=2026").json()
    assert form["editable"] and form["submission"]["status"] == "RETURNED"
    r = save(ipt, "T4/OS1/B", numerator=900, denominator=9000)
    assert r.json()["submission"]["status"] == "RETURNED"  # stays flagged until resubmitted
    r = ipt.post(f"/api/ipt/submissions/{sid}/submit")
    assert r.status_code == 200 and r.json()["submission"]["revision"] == 2
    with SessionLocal() as db:
        actions = [x.action for x in db.query(SubmissionRevision).filter_by(submission_id=sid).order_by(SubmissionRevision.id)]
    assert actions == ["SAVE_DRAFT", "SUBMIT", "RETURN", "SAVE_DRAFT", "RESUBMIT"]
    snaps = [json.loads(x.snapshot_json)["denominator"] for x in SessionLocal().query(SubmissionRevision).filter_by(submission_id=sid)]
    assert 10000 in snaps and 9000 in snaps  # history preserved


def test_10_evidence_upload_validation_and_access(kpt):
    ipt = approved_ipt(kpt)
    other = approved_ipt(kpt)
    sid = save(ipt, "T1/OS1/A", numerator=1, denominator=10).json()["submission"]["id"]
    r = upload(ipt, sid)
    assert r.status_code == 201
    ev = r.json()
    assert ev["sha256"] and ev["name"] == "bukti.pdf"
    assert upload(ipt, sid, "skrip.exe", b"MZ....", "application/octet-stream").status_code == 415
    assert upload(ipt, sid, "palsu.pdf", b"<html>bukan pdf</html>", "application/pdf").status_code == 415
    assert upload(ipt, sid, "../../etc/data.csv", b"a,b\n1,2\n", "text/csv").status_code == 201
    assert upload(ipt, sid, "imej.png", b"\x89PNG\r\n\x1a\n" + b"0" * 20, "image/png").status_code == 201
    # restricted download
    assert ipt.get(f"/api/evidence/{ev['id']}/download").content == PDF_BYTES
    assert other.get(f"/api/evidence/{ev['id']}/download").status_code == 404
    assert kpt.get(f"/api/evidence/{ev['id']}/download").status_code == 200
    # not exposed under /static
    from app.config import settings
    stored = list((settings.evidence_dir / "2026").iterdir())
    assert stored and all(".." not in p.name for p in stored)
    assert kpt.get(f"/static/{stored[0].name}").status_code == 404
    # withdrawn while draft, locked after submission
    assert ipt.post(f"/api/evidence/{ev['id']}/withdraw").status_code == 200
    ev2 = upload(ipt, sid).json()
    ipt.post(f"/api/ipt/submissions/{sid}/submit")
    assert ipt.post(f"/api/evidence/{ev2['id']}/withdraw").status_code == 409
    detail = kpt.get(f"/api/submissions/{sid}").json()
    assert any(e["withdrawn"] for e in detail["evidence"]) and any(e["locked"] for e in detail["evidence"])


def test_upload_size_limit(kpt, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    ipt = approved_ipt(kpt)
    sid = save(ipt, "T1/OS1/A", numerator=1, denominator=10).json()["submission"]["id"]
    big = b"%PDF-1.4\n" + b"0" * (1024 * 1024 + 10)
    assert upload(ipt, sid, data=big).status_code == 413


def test_period_closed_blocks_reporting(kpt):
    ipt = approved_ipt(kpt)
    r = save(ipt, "T1/OS1/A", 2029, numerator=1, denominator=10)
    assert r.status_code == 409 and "tidak dibuka" in r.json()["detail"]


def test_duplicate_record_prevention(kpt):
    ipt = approved_ipt(kpt)
    a = save(ipt, "T1/OS1/A", numerator=1, denominator=10).json()["submission"]["id"]
    b = save(ipt, "T1/OS1/A", numerator=2, denominator=10).json()["submission"]["id"]
    assert a == b  # same institution + KPI + year updates the single record


def test_ipt_overview_counts(kpt):
    ipt = approved_ipt(kpt)
    submit_verified(ipt, kpt, "T1/OS1/A", numerator=450, denominator=10000)
    save(ipt, "T1/OS2/A", numerator=5)
    d = ipt.get("/api/ipt/overview?year=2026").json()
    assert d["total_kpis"] == 20 and d["applicable"] == 19  # KPI 17 is a national milestone in 2026
    assert d["counts"]["VERIFIED"] == 1 and d["counts"]["DRAFT"] == 1 and d["counts"]["NOT_STARTED"] == 17
    assert d["completion_pct"] == round(100 / 19, 1)


def test_note_may_be_null_from_browser(kpt):
    ipt = approved_ipt(kpt)
    r = save(ipt, "T1/OS1/A", numerator=450, denominator=10000, note=None)
    assert r.status_code == 200 and r.json()["submission"]["note"] == ""
