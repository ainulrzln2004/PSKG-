"""Monitoring (KPT), executive analytics and institution-scoped analytics."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import analytics as A
from ..config import INSTITUTION_CATEGORIES, YEARS
from ..db import get_db
from ..kpi_catalogue import TERAS
from ..models import (ROLE_IPT, S_DRAFT, S_RETURNED, S_SUBMITTED, S_VERIFIED, Institution, Kpi,
                      RegistrationApplication, Submission, User)
from ..security import current_user, has_perm, require

router = APIRouter(prefix="/api")


def _year(year: int) -> int:
    if year not in YEARS:
        raise HTTPException(422, "Tahun mesti antara 2026 dan 2030.")
    return year


def _scope(u: User, institution_id: Optional[int], category: Optional[str]) -> tuple[Optional[list[int]], Optional[str], str]:
    if u.role == ROLE_IPT:
        return [u.institution_id], None, "institution"
    if not has_perm(u, "dashboard.executive") and not has_perm(u, "monitoring.view"):
        raise HTTPException(403, "Akses tidak dibenarkan.")
    if category and category not in INSTITUTION_CATEGORIES:
        raise HTTPException(422, "Kategori tidak sah.")
    return ([institution_id] if institution_id else None), (category or None), (
        "institution" if institution_id else "category" if category else "national")


@router.get("/analytics/national")
def national(year: int, teras: Optional[int] = None, kpi_id: Optional[int] = None,
             institution_id: Optional[int] = None, category: Optional[str] = None,
             u: User = Depends(current_user), db: Session = Depends(get_db)):
    ids, cat, scope = _scope(u, institution_id, category)
    ctx = A.Context(db, ids, cat)
    rows = A.national(ctx, _year(year), teras, kpi_id)
    all_rows = rows if not teras and not kpi_id else A.national(ctx, year)
    verified = ctx.submissions(year, S_VERIFIED)
    reported_insts = {s.institution_id for s in ctx.submissions(year) if s.status in (S_SUBMITTED, S_VERIFIED)}
    return {
        "year": year, "scope": scope, "institutions_in_scope": len(ctx.institutions),
        "summary": {
            "institutions": len(ctx.institutions),
            "institutions_reported": len(reported_insts),
            "institutions_not_reported": len(ctx.institutions) - len(reported_insts),
            "verified_reports": len(verified),
            "kpis_met": sum(1 for r in all_rows if r["achieved"] is True),
            "kpis_below": sum(1 for r in all_rows if r["achieved"] is False),
            "kpis_no_data": sum(1 for r in all_rows if r["achieved"] is None),
            "coverage_pct": round(100.0 * len({s.institution_id for s in verified}) / len(ctx.institutions), 1)
            if ctx.institutions else None,
        },
        "kpis": rows,
        "teras": A.teras_breakdown(all_rows),
        "coverage_reference": A.coverage_reference(ctx),
        "note": ("Pencapaian rasmi dikira daripada rekod DISAHKAN sahaja. Rekod yang tiada atau belum disahkan tidak "
                 "dianggap sifar. 'Nasional' bermaksud agregat IPT yang melapor, bukan semestinya liputan nasional penuh."),
    }


@router.get("/analytics/trend")
def trend(kpi_id: int, institution_id: Optional[int] = None, category: Optional[str] = None,
          u: User = Depends(current_user), db: Session = Depends(get_db)):
    ids, cat, scope = _scope(u, institution_id, category)
    ctx = A.Context(db, ids, cat)
    return {"kpi_id": kpi_id, "scope": scope, "points": A.trend(ctx, kpi_id)}


@router.get("/analytics/institutions")
def institution_comparison(kpi_id: int, year: int, category: Optional[str] = None,
                           u: User = Depends(require("dashboard.executive", "monitoring.view")),
                           db: Session = Depends(get_db)):
    ctx = A.Context(db, None, category or None)
    k = db.get(Kpi, kpi_id)
    if not k:
        raise HTTPException(404, "KPI tidak ditemui.")
    t = ctx.target(k.id, _year(year))
    from ..measurement import target_info
    rows = []
    for s in ctx.submissions(year, S_VERIFIED):
        if s.kpi_id != k.id:
            continue
        inst = next(i for i in ctx.institutions if i.id == s.institution_id)
        it = A.institution_targets(db, inst.id, year).get(k.id)
        cmp = A.institution_value(k, s, target_info(t), it)
        rows.append({"institution_id": inst.id, "code": inst.code, "name": inst.name, "category": inst.category,
                     "numerator": s.numerator, "denominator": s.denominator, "value": s.value,
                     "index_excellent": s.index_excellent, **{x: cmp[x] for x in ("achieved", "gap", "comparison")}})
    rows.sort(key=lambda r: (r["value"] is None, -(r["value"] or 0)))
    return {"kpi": {"id": k.id, "code": k.code, "title": k.title, "unit": k.unit}, "year": year,
            "target": target_info(t), "rows": rows,
            "not_reported": [{"code": i.code, "name": i.name} for i in ctx.institutions
                             if i.id not in {r["institution_id"] for r in rows}]}


@router.get("/monitoring/summary")
def monitoring_summary(year: int, u: User = Depends(require("monitoring.view")), db: Session = Depends(get_db)):
    ctx = A.Context(db)
    m = A.status_matrix(ctx, _year(year))
    tot = m["totals"]
    all_insts = db.scalar(select(func.count()).select_from(Institution)) or 0
    reported = sum(1 for r in m["rows"] if r["reported"] > 0)
    incomplete_kpis = 0
    for k in m["kpis"]:
        cells = [r["cells"][k["code"]]["status"] for r in m["rows"]]
        if any(c in ("NOT_STARTED", S_DRAFT, S_RETURNED, S_SUBMITTED) for c in cells):
            incomplete_kpis += 1
    by_teras = []
    for t, name in TERAS.items():
        codes = [k["code"] for k in m["kpis"] if k["teras"] == t]
        c = {}
        for r in m["rows"]:
            for code in codes:
                st = r["cells"][code]["status"]
                c[st] = c.get(st, 0) + 1
        by_teras.append({"teras": t, "name": name, "counts": c})
    return {
        "year": year,
        "institutions_registered": all_insts,
        "institutions_active": len(ctx.institutions),
        "reports_submitted": tot.get(S_SUBMITTED, 0) + tot.get(S_VERIFIED, 0) + tot.get(S_RETURNED, 0),
        "reports_verified": tot.get(S_VERIFIED, 0),
        "reports_pending": tot.get(S_SUBMITTED, 0),
        "reports_returned": tot.get(S_RETURNED, 0),
        "reports_draft": tot.get(S_DRAFT, 0),
        "reports_not_started": tot.get("NOT_STARTED", 0),
        "institutions_not_reported": len(ctx.institutions) - reported,
        "kpis_incomplete": incomplete_kpis,
        "pending_applications": db.scalar(select(func.count()).select_from(RegistrationApplication).where(
            RegistrationApplication.status == "PENDING_APPROVAL")) or 0,
        "by_teras": by_teras,
    }


@router.get("/monitoring/matrix")
def monitoring_matrix(year: int, teras: Optional[int] = None, category: Optional[str] = None,
                      institution_id: Optional[int] = None, status: Optional[str] = None,
                      u: User = Depends(require("monitoring.view")), db: Session = Depends(get_db)):
    ctx = A.Context(db, [institution_id] if institution_id else None, category or None)
    m = A.status_matrix(ctx, _year(year), teras)
    if status:
        m["rows"] = [r for r in m["rows"] if any(c["status"] == status for c in r["cells"].values())]
    return m
