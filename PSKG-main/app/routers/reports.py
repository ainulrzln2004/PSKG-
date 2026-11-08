"""Reports and exports (CSV, XLSX, PDF)."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import analytics as A
from ..config import INSTITUTION_CATEGORIES, YEARS
from ..db import get_db
from ..kpi_catalogue import TERAS
from ..measurement import target_info
from ..models import (ROLE_IPT, S_VERIFIED, Institution, Kpi, Submission, Target, User, VerificationRecord)
from ..security import aware, current_user, has_perm
from ..services import audit
from .dashboards import _scope
from .reporting import STATUS_LABEL

router = APIRouter(prefix="/api/reports")
MYT = timezone(timedelta(hours=8))

REPORTS = {
    "ipt_performance": "Laporan Prestasi IPT",
    "national_kpi": "Laporan KPI Nasional",
    "by_teras": "Laporan Mengikut Teras",
    "target_vs_actual": "Laporan Sasaran vs Pencapaian",
    "reporting_status": "Laporan Status Pelaporan",
    "verification": "Laporan Pengesahan KPT",
    "annual_trend": "Laporan Trend Tahunan",
}
IPT_ALLOWED = {"ipt_performance", "national_kpi", "by_teras", "target_vs_actual", "annual_trend"}
EXEC_ALLOWED = {"national_kpi", "by_teras", "target_vs_actual", "annual_trend"}


def _unit(u: str) -> str:
    return {"percent": "%", "count": "bilangan", "index": "% IPTA"}.get(u, u)


def _fmt(v):
    if v is None:
        return ""
    if isinstance(v, float):
        return round(v, 4)
    return v


def _yesno(v):
    return "" if v is None else ("Ya" if v else "Tidak")


def _target_text(r: dict) -> str:
    if r.get("target_kind") == "milestone":
        return r.get("target_label") or f"{r.get('target')}% (milestone)"
    return "" if r.get("target") is None else r.get("target")


def build(report: str, year: int, u: User, db: Session, institution_id: Optional[int], category: Optional[str],
          teras: Optional[int]) -> tuple[str, list[str], list[list], dict]:
    if report not in REPORTS:
        raise HTTPException(404, "Jenis laporan tidak dikenali.")
    if u.role == ROLE_IPT and report not in IPT_ALLOWED:
        raise HTTPException(403, "Laporan ini tidak dibenarkan untuk Penyelaras IPT.")
    if u.role == "executive" and report not in EXEC_ALLOWED:
        raise HTTPException(403, "Laporan ini tidak dibenarkan untuk peranan anda.")
    ids, cat, scope = _scope(u, institution_id, category)
    ctx = A.Context(db, ids, cat)
    scope_text = {"national": "Nasional (IPT yang melapor)", "category": f"Kategori: {INSTITUTION_CATEGORIES.get(cat or '', cat)}",
                  "institution": "Institusi: " + ", ".join(i.name for i in ctx.institutions)}[scope]
    meta = {"Laporan": REPORTS[report], "Tahun pelaporan": year, "Skop pelaporan": scope_text,
            "Teras": f"Teras {teras}: {TERAS[teras]}" if teras else "Semua",
            "Dijana pada": datetime.now(MYT).strftime("%Y-%m-%d %H:%M (MYT)"), "Dijana oleh": u.name,
            "Nota": "Pencapaian rasmi daripada rekod DISAHKAN sahaja; rekod tiada/belum disahkan tidak dianggap sifar. "
                    "Formula KPI berstatus draf sehingga diperakukan KPT."}

    if report in ("national_kpi", "target_vs_actual", "by_teras"):
        rows_ = A.national(ctx, year, teras)
        if report == "national_kpi":
            cols = ["Tahun", "Teras", "Kod KPI", "KPI", "Unit", "Kaedah agregat", "Σ Pembilang", "Σ Penyebut",
                    "Pencapaian", "Sasaran", "Jurang", "Status sasaran", "IPT melapor (disahkan)", "IPT berkenaan",
                    "Liputan (%)", "Pendua dikecualikan", "Status pengesahan", "Skop"]
            data = [[year, r["teras"], r["code"], r["title"], _unit(r["unit"]), r["method_label"], _fmt(r["numerator_sum"]),
                     _fmt(r["denominator_sum"]), _fmt(r["value"]), _target_text(r), _fmt(r["gap"]),
                     "Capai" if r["achieved"] else "Di bawah sasaran" if r["achieved"] is False else "Tiada data disahkan",
                     r["reporting"], r["applicable"], _fmt(r["coverage_pct"]), r["duplicates_excluded"],
                     "Disahkan sahaja", scope_text] for r in rows_]
        elif report == "target_vs_actual":
            cols = ["Tahun", "Kod KPI", "KPI", "Unit", "Sasaran", "Pencapaian", "Jurang", "% sasaran dicapai",
                    "Capai sasaran", "Liputan (%)", "Status pengesahan", "Skop"]
            data = [[year, r["code"], r["title"], _unit(r["unit"]), _target_text(r), _fmt(r["value"]), _fmt(r["gap"]),
                     _fmt(r["pct_of_target"]), _yesno(r["achieved"]), _fmt(r["coverage_pct"]), "Disahkan sahaja",
                     scope_text] for r in rows_]
        else:
            cols = ["Tahun", "Teras", "Nama Teras", "Kod KPI", "KPI", "Pencapaian", "Sasaran", "Jurang", "Capai",
                    "Liputan (%)", "Status pengesahan", "Skop"]
            data = []
            for t, name in TERAS.items():
                for r in [x for x in rows_ if x["teras"] == t]:
                    data.append([year, t, name, r["code"], r["title"], _fmt(r["value"]), _target_text(r), _fmt(r["gap"]),
                                 _yesno(r["achieved"]), _fmt(r["coverage_pct"]), "Disahkan sahaja", scope_text])
            for b in A.teras_breakdown(rows_):
                if teras and b["teras"] != teras:
                    continue
                data.append([year, b["teras"], b["name"], "RINGKASAN", f"{b['kpis']} KPI", "", "", "",
                             f"Capai {b['met']} · Bawah {b['below']} · Tiada data {b['no_data']}", "", "", scope_text])
        return REPORTS[report], cols, data, meta

    if report == "annual_trend":
        cols = ["Kod KPI", "KPI", "Unit"] + [f"Pencapaian {y}" for y in YEARS] + [f"Sasaran {y}" for y in YEARS] + ["Skop"]
        data = []
        for k in ctx.kpis:
            if teras and k.teras != teras:
                continue
            pts = A.trend(ctx, k.id)
            data.append([k.code, k.title, _unit(k.unit)] + [_fmt(p["value"]) for p in pts] +
                        [_target_text(p) for p in pts] + [scope_text])
        meta["Tahun pelaporan"] = "2026–2030"
        return REPORTS[report], cols, data, meta

    if report == "ipt_performance":
        if u.role != ROLE_IPT and not has_perm(u, "submissions.view_all"):
            raise HTTPException(403, "Laporan ini tidak dibenarkan untuk peranan anda.")
        cols = ["Tahun", "Kod IPT", "Nama IPT", "Kod KPI", "KPI", "Unit", "Pembilang", "Penyebut", "Pencapaian",
                "Sasaran nasional", "Jurang", "Status pelaporan", "Semakan", "Ulasan KPT", "Skop"]
        subs = {(s.institution_id, s.kpi_id): s for s in ctx.submissions(year)}
        data = []
        for inst in ctx.institutions:
            for k in ctx.kpis:
                if teras and k.teras != teras:
                    continue
                t = ctx.target(k.id, year)
                ok, _ = A.applicability(k, inst, t)
                s = subs.get((inst.id, k.id))
                st = s.status if s else ("NOT_STARTED" if ok else "NOT_APPLICABLE")
                tinfo = target_info(t)
                cmp = A.institution_value(k, s, tinfo, None) if s else {"gap": None}
                data.append([year, inst.code, inst.name, k.code, k.title, _unit(k.unit),
                             _fmt(s.numerator) if s else "", _fmt(s.denominator) if s else "",
                             _fmt(s.value) if s else "", _target_text({"target": tinfo["value"], "target_kind": tinfo["kind"],
                                                                         "target_label": tinfo["label"]}),
                             _fmt(cmp["gap"]) if (s and k.unit == "percent") else "", STATUS_LABEL.get(st, st),
                             "Disahkan" if st == S_VERIFIED else "Belum disahkan", (s.review_note if s else "") or "",
                             scope_text])
        return REPORTS[report], cols, data, meta

    if not has_perm(u, "monitoring.view"):
        raise HTTPException(403, "Laporan ini tidak dibenarkan untuk peranan anda.")
    if report == "reporting_status":
        m = A.status_matrix(ctx, year, teras)
        cols = ["Tahun", "Kod IPT", "Nama IPT", "Kategori", "Kod KPI", "Status pelaporan", "Nilai disahkan",
                "Lengkap (%) institusi", "Skop"]
        data = [[year, r["code"], r["name"], INSTITUTION_CATEGORIES.get(r["category"] or "", "—"), code,
                 STATUS_LABEL.get(c["status"], c["status"]), _fmt(c["value"]), _fmt(r["completion_pct"]), scope_text]
                for r in m["rows"] for code, c in r["cells"].items()]
        return REPORTS[report], cols, data, meta

    # verification
    cols = ["Tarikh keputusan", "Tahun", "Kod IPT", "Nama IPT", "Kod KPI", "Revisi", "Keputusan", "Nilai semasa keputusan",
            "Ulasan", "Penyemak", "Skop"]
    kpis = {k.id: k for k in ctx.kpis}
    insts = {i.id: i for i in ctx.institutions}
    data = []
    q = select(VerificationRecord, Submission).join(Submission, Submission.id == VerificationRecord.submission_id) \
        .where(Submission.year == year).order_by(VerificationRecord.at)
    for v, s in db.execute(q):
        if s.institution_id not in insts or (teras and kpis[s.kpi_id].teras != teras):
            continue
        reviewer = db.get(User, v.reviewer_id)
        data.append([aware(v.at).astimezone(MYT).strftime("%Y-%m-%d %H:%M"), year, insts[s.institution_id].code,
                     insts[s.institution_id].name, kpis[s.kpi_id].code, v.revision,
                     {"VERIFIED": "Disahkan", "RETURNED": "Dipulangkan", "REOPENED": "Dibuka semula"}.get(v.decision, v.decision),
                     _fmt(v.value_at_decision), v.comment or "", reviewer.name if reviewer else "", scope_text])
    return REPORTS[report], cols, data, meta


# ------------------------------------------------------------------ writers
def to_csv(title, cols, data, meta) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    for k, v in meta.items():
        w.writerow([k, v])
    w.writerow([])
    w.writerow(cols)
    for row in data:
        w.writerow(["" if c is None else c for c in row])
    return ("﻿" + buf.getvalue()).encode("utf-8")


def to_xlsx(title, cols, data, meta) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    wb = Workbook()
    ws = wb.active
    ws.title = "Laporan"
    ws.append(["PSKG Monitor 2030 — " + title])
    ws["A1"].font = Font(bold=True, size=14, color="10284A")
    for k, v in meta.items():
        ws.append([k, v])
    ws.append([])
    ws.append(cols)
    hdr = ws.max_row
    for c in ws[hdr]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="10284A")
        c.alignment = Alignment(wrap_text=True, vertical="top")
    for row in data:
        ws.append(["" if c is None else c for c in row])
    for i, col in enumerate(cols, 1):
        width = max([len(str(col))] + [len(str(r[i - 1])) for r in data[:300]] + [8])
        ws.column_dimensions[get_column_letter(i)].width = min(width + 2, 60)
    ws.freeze_panes = ws.cell(row=hdr + 1, column=1)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def to_pdf(title, cols, data, meta) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=landscape(A4), leftMargin=10 * mm, rightMargin=10 * mm,
                            topMargin=10 * mm, bottomMargin=10 * mm, title=title)
    ss = getSampleStyleSheet()
    small = ss["BodyText"].clone("small", fontSize=6.5, leading=8)
    head = ss["BodyText"].clone("head", fontSize=6.5, leading=8, textColor=colors.white, fontName="Helvetica-Bold")
    story = [Paragraph(f"PSKG Monitor 2030 — {title}", ss["Title"])]
    for k, v in meta.items():
        story.append(Paragraph(f"<b>{k}:</b> {str(v).replace('&', '&amp;').replace('<', '&lt;')}", ss["BodyText"]))
    story.append(Spacer(1, 4 * mm))

    def P(x, st):
        return Paragraph(str("" if x is None else x).replace("&", "&amp;").replace("<", "&lt;"), st)
    table = Table([[P(c, head) for c in cols]] + [[P(c, small) for c in r] for r in data] or [[""]], repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#10284A")),
                               ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C8D3E0")),
                               ("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F6FA")])]))
    story.append(table)
    doc.build(story)
    return out.getvalue()


@router.get("")
def catalogue(u: User = Depends(current_user)):
    allowed = IPT_ALLOWED if u.role == ROLE_IPT else EXEC_ALLOWED if u.role == "executive" else set(REPORTS)
    return [{"key": k, "title": v} for k, v in REPORTS.items() if k in allowed]


@router.get("/{report}")
def export(report: str, request: Request, year: int = 2026, format: str = "csv", institution_id: Optional[int] = None,
           category: Optional[str] = None, teras: Optional[int] = None, u: User = Depends(current_user),
           db: Session = Depends(get_db)):
    if year not in YEARS:
        raise HTTPException(422, "Tahun tidak sah.")
    if teras is not None and teras not in TERAS:
        raise HTTPException(422, "Teras tidak sah.")
    title, cols, data, meta = build(report, year, u, db, institution_id, category, teras)
    fmt = format.lower()
    stamp = datetime.now(MYT).strftime("%Y%m%d_%H%M")
    base = f"PSKG_{report}_{year}_{stamp}"
    if fmt == "csv":
        body, media = to_csv(title, cols, data, meta), "text/csv; charset=utf-8"
    elif fmt == "xlsx":
        body, media = to_xlsx(title, cols, data, meta), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif fmt == "pdf":
        body, media = to_pdf(title, cols, data, meta), "application/pdf"
    elif fmt == "json":
        return {"title": title, "columns": cols, "rows": data, "meta": meta}
    else:
        raise HTTPException(422, "Format mesti csv, xlsx atau pdf.")
    audit(db, u, "report_exported", f"report:{report}", request, year=year, format=fmt, rows=len(data))
    db.commit()
    return Response(body, media_type=media, headers={"Content-Disposition": f'attachment; filename="{base}.{fmt}"',
                                                     "Cache-Control": "no-store"})
