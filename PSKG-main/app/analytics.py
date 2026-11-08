"""National / institutional aggregation and reporting completeness.

Rules (see README "Pengagregatan"):
  * Only VERIFIED submissions contribute to official achievements.
  * Percentage KPIs: 100 × Σ numerator ÷ Σ denominator (pooled), never an average of percentages.
  * Count KPIs: Σ counts; itemised KPIs count DISTINCT references so duplicates across IPT are excluded.
  * Employer Satisfaction Index: milestone years use the KPT-recorded national milestone;
    later years use 100 × (#IPTA with excellent score) ÷ (#IPTA reporting verified scores).
  * Missing / unverified records are never treated as zero; coverage is always reported.
"""
from __future__ import annotations

import json
from collections import defaultdict
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import OFFICIAL_INSTITUTION_POPULATION, YEARS
from .kpi_catalogue import TERAS
from .measurement import achievement_vs_target, applicability, cfg, target_info
from .models import (S_NOT_APPLICABLE, S_NOT_STARTED, S_VERIFIED, Institution, InstitutionTarget, Kpi,
                     KpiMilestone, Submission, Target)

METHOD_LABEL = {
    "pooled_ratio": "100 × Σ pembilang ÷ Σ penyebut (rekod disahkan)",
    "sum": "Σ bilangan (rekod disahkan)",
    "sum_distinct_items": "Bilangan rujukan unik (pendua dikecualikan)",
    "share_of_institutions": "100 × IPTA skor cemerlang ÷ IPTA melapor (disahkan)",
    "milestone": "Kemajuan pembangunan indeks (milestone nasional direkod KPT)",
}


class Context:
    """Loads the reference data needed for analytics once per request."""

    def __init__(self, db: Session, institution_ids: Optional[Iterable[int]] = None,
                 category: Optional[str] = None, include_inactive: bool = False):
        self.db = db
        self.kpis = list(db.scalars(select(Kpi).order_by(Kpi.sort_order, Kpi.id)))
        self.targets = {(t.kpi_id, t.year): t for t in db.scalars(select(Target))}
        q = select(Institution)
        if not include_inactive:
            q = q.where(Institution.status == "ACTIVE")
        if category:
            q = q.where(Institution.category == category)
        if institution_ids:
            q = q.where(Institution.id.in_(list(institution_ids)))
        self.institutions = list(db.scalars(q.order_by(Institution.name)))
        self.inst_ids = {i.id for i in self.institutions}
        self.milestones = {(m.kpi_id, m.year): m for m in db.scalars(select(KpiMilestone))}

    def target(self, kpi_id: int, year: int) -> Optional[Target]:
        return self.targets.get((kpi_id, year))

    def submissions(self, year: Optional[int] = None, status: Optional[str] = None) -> list[Submission]:
        if not self.inst_ids:
            return []
        q = select(Submission).where(Submission.institution_id.in_(self.inst_ids))
        if year is not None:
            q = q.where(Submission.year == year)
        if status:
            q = q.where(Submission.status == status)
        return list(self.db.scalars(q))


def _items(s: Submission) -> list[dict]:
    try:
        return (json.loads(s.details_json or "{}") or {}).get("items") or []
    except ValueError:
        return []


def aggregate_kpi(ctx: Context, k: Kpi, year: int, verified: list[Submission]) -> dict:
    t = ctx.target(k.id, year)
    tinfo = target_info(t)
    applicable = [i for i in ctx.institutions if applicability(k, i, t)[0]]
    app_ids = {i.id for i in applicable}
    subs = [s for s in verified if s.kpi_id == k.id and s.year == year and s.institution_id in app_ids]
    out = {
        "kpi_id": k.id, "code": k.code, "title": k.title, "teras": k.teras, "unit": k.unit, "year": year,
        "target": tinfo["value"], "target_kind": tinfo["kind"], "target_label": tinfo["label"],
        "value": None, "numerator_sum": None, "denominator_sum": None, "duplicates_excluded": 0,
        "reporting": len(subs), "applicable": len(applicable),
        "coverage_pct": round(100.0 * len(subs) / len(applicable), 1) if applicable else None,
        "method": k.aggregation, "method_label": METHOD_LABEL.get(k.aggregation or "", ""),
    }
    if tinfo["kind"] == "milestone":
        m = ctx.milestones.get((k.id, year))
        out.update(method="milestone", method_label=METHOD_LABEL["milestone"], reporting=0, applicable=0,
                   coverage_pct=None, value=m.progress_pct if m else None,
                   milestone_note=m.note if m else None)
        if m is not None:
            out.update(achievement_vs_target("percent", m.progress_pct, {"value": tinfo["value"], "kind": "value"}))
        else:
            out.update(achieved=None, gap=None, pct_of_target=None)
        return out
    if k.aggregation == "pooled_ratio":
        valid = [s for s in subs if s.numerator is not None and s.denominator]
        if valid:
            n = sum(s.numerator for s in valid)
            d = sum(s.denominator for s in valid)
            out.update(numerator_sum=n, denominator_sum=d, value=round(100.0 * n / d, 4) if d else None)
    elif k.aggregation == "sum_distinct_items":
        refs, fallback, total_items = set(), 0.0, 0
        for s in subs:
            items = _items(s)
            if items:
                total_items += len(items)
                refs.update("".join(str(i.get("ref", "")).upper().split()) or f"#{s.id}:{n}" for n, i in enumerate(items))
            elif s.numerator is not None:
                fallback += s.numerator
        if subs:
            out.update(value=float(len(refs)) + fallback, numerator_sum=float(len(refs)) + fallback,
                       duplicates_excluded=total_items - len(refs))
    elif k.aggregation == "sum":
        vals = [s.numerator for s in subs if s.numerator is not None]
        if vals:
            out.update(value=float(sum(vals)), numerator_sum=float(sum(vals)))
    elif k.aggregation == "share_of_institutions":
        scored = [s for s in subs if s.index_excellent is not None]
        if scored:
            exc = sum(1 for s in scored if s.index_excellent)
            out.update(numerator_sum=float(exc), denominator_sum=float(len(scored)),
                       value=round(100.0 * exc / len(scored), 4))
    out.update(achievement_vs_target(k.unit, out["value"], tinfo))
    return out


def national(ctx: Context, year: int, teras: Optional[int] = None, kpi_id: Optional[int] = None) -> list[dict]:
    verified = ctx.submissions(year, S_VERIFIED)
    rows = []
    for k in ctx.kpis:
        if teras and k.teras != teras:
            continue
        if kpi_id and k.id != kpi_id:
            continue
        rows.append(aggregate_kpi(ctx, k, year, verified))
    return rows


def trend(ctx: Context, kpi_id: int) -> list[dict]:
    k = next((x for x in ctx.kpis if x.id == kpi_id), None)
    if not k:
        return []
    verified = ctx.submissions(None, S_VERIFIED)
    return [aggregate_kpi(ctx, k, y, verified) for y in YEARS]


def institution_value(k: Kpi, s: Submission, target: dict, inst_target: Optional[float]) -> dict:
    """Per-institution result and comparison. National COUNT targets are never used as quotas."""
    res = {"value": s.value, "achieved": None, "gap": None, "pct_of_target": None, "comparison": None}
    if k.unit == "percent":
        res.update(achievement_vs_target("percent", s.value, target))
        res["comparison"] = "Sasaran nasional (kadar rujukan)"
    elif k.unit == "count":
        if inst_target is not None:
            res.update(achievement_vs_target("count", s.value, {"value": inst_target, "kind": "value"}))
            res["comparison"] = "Sasaran institusi (ditetapkan KPT)"
        else:
            res["comparison"] = "Tiada sasaran institusi — sasaran nasional bukan kuota IPT"
    elif k.unit == "index":
        res["achieved"] = s.index_excellent
        res["comparison"] = "Skor cemerlang (≥ ambang indeks)"
    return res


def institution_targets(db: Session, institution_id: int, year: int) -> dict[int, float]:
    return {t.kpi_id: t.value for t in db.scalars(select(InstitutionTarget).where(
        InstitutionTarget.institution_id == institution_id, InstitutionTarget.year == year))}


def status_matrix(ctx: Context, year: int, teras: Optional[int] = None) -> dict:
    subs = {(s.institution_id, s.kpi_id): s for s in ctx.submissions(year)}
    kpis = [k for k in ctx.kpis if not teras or k.teras == teras]
    rows, totals = [], defaultdict(int)
    for inst in ctx.institutions:
        cells = {}
        for k in kpis:
            ok, reason = applicability(k, inst, ctx.target(k.id, year))
            if not ok:
                st = S_NOT_APPLICABLE
            else:
                s = subs.get((inst.id, k.id))
                st = s.status if s else S_NOT_STARTED
            totals[st] += 1
            s = subs.get((inst.id, k.id))
            cells[k.code] = {"status": st, "submission_id": s.id if s else None,
                             "value": s.value if (s and st == S_VERIFIED) else None}
        applicable = sum(1 for c in cells.values() if c["status"] != S_NOT_APPLICABLE)
        reported = sum(1 for c in cells.values() if c["status"] in ("SUBMITTED", "VERIFIED"))
        verified = sum(1 for c in cells.values() if c["status"] == "VERIFIED")
        rows.append({"institution_id": inst.id, "code": inst.code, "name": inst.name, "category": inst.category,
                     "cells": cells, "applicable": applicable, "reported": reported, "verified": verified,
                     "completion_pct": round(100.0 * reported / applicable, 1) if applicable else None})
    return {"year": year, "kpis": [{"id": k.id, "code": k.code, "title": k.title, "teras": k.teras} for k in kpis],
            "rows": rows, "totals": dict(totals)}


def teras_breakdown(rows: list[dict]) -> list[dict]:
    out = []
    for t, name in TERAS.items():
        rs = [r for r in rows if r["teras"] == t]
        out.append({"teras": t, "name": name, "kpis": len(rs),
                    "met": sum(1 for r in rs if r["achieved"] is True),
                    "below": sum(1 for r in rs if r["achieved"] is False),
                    "no_data": sum(1 for r in rs if r["achieved"] is None)})
    return out


def coverage_reference(ctx: Context) -> dict:
    by_cat = defaultdict(int)
    for i in ctx.institutions:
        by_cat[i.category or "-"] += 1
    return {"registered_by_category": dict(by_cat), "official_population": OFFICIAL_INSTITUTION_POPULATION}
