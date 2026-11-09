"""Aggregation and dashboard rules (prompt §21 'Executive Dashboard')."""
from conftest import approved_ipt, kpi_id, save, submit_verified, upload

from app import analytics as A
from app.db import SessionLocal


def _ctx(ids):
    db = SessionLocal()
    return db, A.Context(db, ids)


def _row(ctx, code, year=2026):
    return next(r for r in A.national(ctx, year) if r["code"] == code)


def test_1_only_verified_data_is_used(kpt):
    a, b = approved_ipt(kpt), approved_ipt(kpt)
    submit_verified(a, kpt, "T1/OS2/A", numerator=100, denominator=1000)
    sid = save(b, "T1/OS2/A", numerator=900, denominator=1000).json()["submission"]["id"]
    upload(b, sid)
    b.post(f"/api/ipt/submissions/{sid}/submit")  # submitted but NOT verified
    db, ctx = _ctx([a.institution_id, b.institution_id])
    r = _row(ctx, "T1/OS2/A")
    assert r["value"] == 10.0 and r["reporting"] == 1 and r["applicable"] == 2 and r["coverage_pct"] == 50.0
    db.close()


def test_2_percentage_pooled_not_average(kpt):
    a, b = approved_ipt(kpt), approved_ipt(kpt)
    submit_verified(a, kpt, "T1/OS1/A", numerator=450, denominator=10000)   # 4.5 %
    submit_verified(b, kpt, "T1/OS1/A", numerator=90, denominator=1000)     # 9.0 %
    db, ctx = _ctx([a.institution_id, b.institution_id])
    r = _row(ctx, "T1/OS1/A")
    assert r["numerator_sum"] == 540 and r["denominator_sum"] == 11000
    assert abs(r["value"] - 100 * 540 / 11000) < 1e-3          # 4.909 %, not the mean 6.75 %
    assert r["achieved"] is True and abs(r["gap"] - (r["value"] - 2)) < 1e-3
    db.close()


def test_3_counts_aggregated_and_itemised_duplicates_excluded(kpt):
    a, b = approved_ipt(kpt), approved_ipt(kpt)
    submit_verified(a, kpt, "T5/OS1/C", numerator=180)
    submit_verified(b, kpt, "T5/OS1/C", numerator=150)
    shared = {"ref": "MY-PI2026-777", "title": "Produk bersama", "ip_type": "Paten"}
    submit_verified(a, kpt, "T3/OS1/A", items=[shared, {"ref": "MY-PI2026-001", "title": "X", "ip_type": "Paten"}], attestations=[True])
    submit_verified(b, kpt, "T3/OS1/A", items=[{**shared, "ref": "my-pi2026-777"}], attestations=[True])
    db, ctx = _ctx([a.institution_id, b.institution_id])
    assert _row(ctx, "T5/OS1/C")["value"] == 330 and _row(ctx, "T5/OS1/C")["achieved"] is True
    ip = _row(ctx, "T3/OS1/A")
    assert ip["value"] == 2 and ip["duplicates_excluded"] == 1
    db.close()


def test_4_institution_comparison(kpt, executive):
    a, b = approved_ipt(kpt), approved_ipt(kpt)
    submit_verified(a, kpt, "T4/OS1/A", numerator=30, denominator=1000)
    submit_verified(b, kpt, "T4/OS1/A", numerator=5, denominator=1000)
    r = executive.get(f"/api/analytics/institutions?kpi_id={kpi_id('T4/OS1/A')}&year=2026").json()
    mine = {x["institution_id"]: x for x in r["rows"] if x["institution_id"] in (a.institution_id, b.institution_id)}
    assert mine[a.institution_id]["value"] == 3.0 and mine[a.institution_id]["achieved"] is True
    assert mine[b.institution_id]["value"] == 0.5 and mine[b.institution_id]["achieved"] is False
    vals = [x["value"] for x in r["rows"]]
    assert vals == sorted(vals, reverse=True)


def test_5_year_filter(kpt, executive):
    a = approved_ipt(kpt)
    submit_verified(a, kpt, "T5/OS1/B", numerator=60, denominator=1000)
    d26 = executive.get(f"/api/analytics/national?year=2026&institution_id={a.institution_id}").json()
    d27 = executive.get(f"/api/analytics/national?year=2027&institution_id={a.institution_id}").json()
    r26 = next(r for r in d26["kpis"] if r["code"] == "T5/OS1/B")
    r27 = next(r for r in d27["kpis"] if r["code"] == "T5/OS1/B")
    assert r26["value"] == 6.0 and r26["target"] == 5 and r27["value"] is None and r27["target"] == 15
    trend = executive.get(f"/api/analytics/trend?kpi_id={kpi_id('T5/OS1/B')}&institution_id={a.institution_id}").json()
    assert [p["value"] for p in trend["points"]] == [6.0, None, None, None, None]
    assert executive.get("/api/analytics/national?year=2031").status_code == 422


def test_6_reporting_completeness(kpt):
    a, b = approved_ipt(kpt), approved_ipt(kpt, "POLITEKNIK")
    submit_verified(a, kpt, "T1/OS1/A", numerator=1, denominator=10)
    save(b, "T1/OS1/A", numerator=1)
    db, ctx = _ctx([a.institution_id, b.institution_id])
    m = A.status_matrix(ctx, 2026)
    rows = {r["institution_id"]: r for r in m["rows"]}
    assert rows[a.institution_id]["cells"]["T1/OS1/A"]["status"] == "VERIFIED"
    assert rows[b.institution_id]["cells"]["T1/OS1/A"]["status"] == "DRAFT"
    assert rows[a.institution_id]["cells"]["T1/OS2/A"]["status"] == "NOT_STARTED"
    assert rows[a.institution_id]["cells"]["T4/OS2/B"]["status"] == "NOT_APPLICABLE"
    assert rows[a.institution_id]["applicable"] == 19 and rows[a.institution_id]["completion_pct"] == round(100 / 19, 1)
    db.close()
    # API matrix for KPT
    mx = kpt.get(f"/api/monitoring/matrix?year=2026&institution_id={a.institution_id}").json()
    assert len(mx["rows"]) == 1 and len(mx["kpis"]) == 20


def test_7_missing_data_not_treated_as_zero(kpt):
    a, b = approved_ipt(kpt), approved_ipt(kpt)
    submit_verified(a, kpt, "T2/OS1/B", numerator=0, denominator=100)  # a verified zero
    db, ctx = _ctx([a.institution_id, b.institution_id])
    r = _row(ctx, "T2/OS1/B")
    assert r["value"] == 0.0 and r["reporting"] == 1 and r["applicable"] == 2
    none = _row(ctx, "T2/OS2/B")
    assert none["value"] is None and none["achieved"] is None and none["reporting"] == 0
    m = A.status_matrix(ctx, 2026)
    cell = {x["institution_id"]: x for x in m["rows"]}
    assert cell[a.institution_id]["cells"]["T2/OS1/B"] == {"status": "VERIFIED", "submission_id": cell[a.institution_id]["cells"]["T2/OS1/B"]["submission_id"], "value": 0.0}
    assert cell[b.institution_id]["cells"]["T2/OS1/B"]["status"] == "NOT_STARTED"
    db.close()


def test_kpi17_milestone_and_share_aggregation(kpt, admin):
    from conftest import open_period
    open_period(2028)
    a, b = approved_ipt(kpt, "UA"), approved_ipt(kpt, "UA")
    r = admin.put(f"/api/admin/kpis/{kpi_id('T4/OS2/B')}/milestone", json={"year": 2026, "progress_pct": 40, "note": "Instrumen dirangka"})
    assert r.status_code == 200
    assert admin.put(f"/api/admin/kpis/{kpi_id('T4/OS2/B')}/milestone", json={"year": 2028, "progress_pct": 40}).status_code == 422
    submit_verified(a, kpt, "T4/OS2/B", 2028, index_score=4.4)
    submit_verified(b, kpt, "T4/OS2/B", 2028, index_score=3.1)
    db, ctx = _ctx([a.institution_id, b.institution_id])
    m26 = _row(ctx, "T4/OS2/B", 2026)
    assert m26["method"] == "milestone" and m26["value"] == 40 and m26["achieved"] is False  # 40 % vs 50 % milestone
    r28 = _row(ctx, "T4/OS2/B", 2028)
    assert r28["value"] == 50.0 and r28["target"] == 60 and r28["achieved"] is False
    db.close()


def test_monitoring_summary_and_permissions(kpt, executive):
    d = kpt.get("/api/monitoring/summary?year=2026").json()
    for key in ("institutions_registered", "institutions_active", "reports_submitted", "reports_verified",
                "reports_pending", "reports_returned", "institutions_not_reported", "kpis_incomplete"):
        assert key in d
    assert executive.get("/api/monitoring/summary?year=2026").status_code == 403
    assert executive.get("/api/analytics/national?year=2026").status_code == 200
