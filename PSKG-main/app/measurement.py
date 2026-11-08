"""Server-side KPI measurement: applicability, validation and calculation.

All calculation happens here (never trusted from the browser).
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any, Optional

from fastapi import HTTPException

from .models import Institution, Kpi, Target


def cfg(k: Kpi) -> dict:
    try:
        return json.loads(k.config_json or "{}")
    except ValueError:
        return {}


def notes(k: Kpi) -> list[str]:
    try:
        return json.loads(k.confirmation_notes or "[]")
    except ValueError:
        return []


def target_info(t: Optional[Target]) -> dict:
    if t is None:
        return {"value": None, "kind": "value", "label": None}
    return {"value": t.value, "kind": t.kind or "value", "label": t.label}


def applicability(k: Kpi, inst: Optional[Institution], target: Optional[Target]) -> tuple[bool, Optional[str]]:
    """Is this KPI reportable by this institution for the target's year?"""
    if target is not None and (target.kind or "value") == "milestone":
        return False, ("Fasa pembangunan indeks (milestone nasional) — kemajuan direkod oleh KPT, "
                       "bukan dilaporkan oleh IPT.")
    cats = cfg(k).get("applicable_categories")
    if cats and inst is not None:
        if not inst.category:
            return False, "Kategori institusi belum ditetapkan oleh KPT; kebolehgunaan KPI tidak dapat ditentukan."
        if inst.category not in cats:
            return False, "KPI ini hanya terpakai kepada IPTA (Universiti Awam) mengikut takrif slaid 26 — perlu pengesahan KPT."
    return True, None


@dataclass
class Measurement:
    numerator: Optional[float] = None
    denominator: Optional[float] = None
    value: Optional[float] = None
    index_score: Optional[float] = None
    index_excellent: Optional[bool] = None
    details: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)
    complete: bool = False


def _num(raw: Any, label: str, integer: bool = True) -> Optional[float]:
    if raw is None or raw == "":
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        raise HTTPException(422, f"{label} mesti nombor.")
    if math.isnan(v) or math.isinf(v):
        raise HTTPException(422, f"{label} tidak sah.")
    if v < 0:
        raise HTTPException(422, f"{label} tidak boleh negatif.")
    if integer and not float(v).is_integer():
        raise HTTPException(422, f"{label} mesti nombor bulat.")
    if v > 1e9:
        raise HTTPException(422, f"{label} terlalu besar.")
    return v


def _norm_ref(ref: str) -> str:
    return "".join(str(ref).upper().split())


def measure(k: Kpi, payload: dict, final: bool) -> Measurement:
    """Validate the inputs for KPI `k` and compute the achievement.

    final=False  -> draft: incomplete inputs allowed, provided values still validated.
    final=True   -> submission: all required inputs must be complete and valid.
    """
    c = cfg(k)
    m = Measurement()
    attest_texts = c.get("attestations") or []
    attest = payload.get("attestations") or []
    if not isinstance(attest, list):
        raise HTTPException(422, "Format pengesahan kelayakan tidak sah.")
    m.details["attestations"] = [bool(attest[i]) if i < len(attest) else False for i in range(len(attest_texts))]

    if k.unit == "percent":
        m.numerator = _num(payload.get("numerator"), "Pembilang (A)")
        m.denominator = _num(payload.get("denominator"), "Penyebut (B)")
        if m.denominator is not None and m.denominator == 0:
            raise HTTPException(422, "Penyebut (B) mesti lebih besar daripada sifar.")
        if m.numerator is not None and m.denominator is not None:
            if m.numerator > m.denominator:
                if k.subset_ratio:
                    raise HTTPException(422, "Pembilang (A) tidak boleh melebihi Penyebut (B) bagi KPI ini.")
                m.warnings.append("Pembilang melebihi penyebut. Formula rasmi menggunakan populasi berbeza "
                                  "(graduan ÷ enrolmen) — sila semak semula sebelum menghantar.")
            m.value = round(100.0 * m.numerator / m.denominator, 4)
        m.complete = m.value is not None
        if final and not m.complete:
            raise HTTPException(422, "Pembilang (A) dan Penyebut (B) wajib diisi sebelum dihantar.")

    elif k.unit == "count":
        if k.itemised:
            items = payload.get("items") or []
            if not isinstance(items, list) or len(items) > 2000:
                raise HTTPException(422, "Senarai item tidak sah.")
            schema = c.get("items_schema") or []
            clean, seen = [], set()
            for i, it in enumerate(items, 1):
                if not isinstance(it, dict):
                    raise HTTPException(422, f"Item {i} tidak sah.")
                row = {f["key"]: str(it.get(f["key"], "") or "").strip()[:300] for f in schema}
                if not any(row.values()):
                    continue
                missing = [f["label"] for f in schema if f.get("required") and not row.get(f["key"])]
                if missing and final:
                    raise HTTPException(422, f"Item {i}: {', '.join(missing)} wajib diisi.")
                ref = _norm_ref(row.get("ref", ""))
                if ref:
                    if ref in seen:
                        raise HTTPException(422, f"Item {i}: rujukan '{row['ref']}' berulang dalam laporan ini.")
                    seen.add(ref)
                clean.append(row)
            m.details["items"] = clean
            given = _num(payload.get("numerator"), "Bilangan sebenar")
            if clean:
                m.numerator = float(len(clean))  # count is always derived from the itemised list
                if given is not None and given != len(clean):
                    m.warnings.append("Bilangan dikira semula daripada senarai item.")
            elif given is None:
                m.numerator = None
            elif given == 0:
                m.numerator = 0.0
            else:
                if final:
                    raise HTTPException(422, "Senaraikan setiap item (rujukan unik) supaya kiraan boleh disemak dan "
                                             "pendua dikecualikan.")
                m.numerator = given
        else:
            m.numerator = _num(payload.get("numerator"), "Bilangan sebenar")
        m.value = m.numerator
        m.complete = m.value is not None
        if final and not m.complete:
            raise HTTPException(422, "Bilangan sebenar wajib diisi sebelum dihantar (isi 0 jika tiada).")

    elif k.unit == "index":
        lo, hi = (c.get("index_scale") or [1, 5])
        score = _num(payload.get("index_score"), "Skor indeks", integer=False)
        if score is not None and not (lo <= score <= hi):
            raise HTTPException(422, f"Skor indeks mesti dalam julat {lo}–{hi}.")
        m.index_score = score
        thr = c.get("excellence_threshold")
        if score is not None and thr is not None:
            m.index_excellent = score >= float(thr)
        elif payload.get("index_excellent") is not None:
            m.index_excellent = bool(payload.get("index_excellent"))
        m.value = score
        m.complete = score is not None and m.index_excellent is not None
        if final and not m.complete:
            raise HTTPException(422, "Skor Indeks Kepuasan Majikan institusi wajib diisi sebelum dihantar.")
    else:
        raise HTTPException(500, "Jenis pengukuran KPI tidak dikenali.")

    if final and attest_texts and not all(m.details["attestations"]):
        raise HTTPException(422, "Sila sahkan semua syarat kelayakan KPI sebelum menghantar.")
    return m


def achievement_vs_target(unit: str, value: Optional[float], target: dict) -> dict:
    """Gap and % of target for a value against a numeric target (milestones are not compared)."""
    tv = target.get("value")
    if value is None or tv is None or target.get("kind") == "milestone":
        return {"achieved": None, "gap": None, "pct_of_target": None}
    gap = round(value - tv, 4)
    return {"achieved": value >= tv, "gap": gap, "pct_of_target": round(100.0 * value / tv, 2) if tv else None}
