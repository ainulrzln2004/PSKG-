"""KPI catalogue, IPT reporting workflow, supporting documents and KPT verification."""
from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..analytics import institution_targets, institution_value
from ..config import YEARS, settings
from ..db import get_db
from ..kpi_catalogue import TERAS
from ..measurement import applicability, cfg, measure, notes, target_info
from ..models import (ROLE_IPT, S_DRAFT, S_NOT_APPLICABLE, S_NOT_STARTED, S_RETURNED, S_SUBMITTED, S_VERIFIED,
                      EvidenceFile, Institution, Kpi, ReportingPeriod, Submission, SubmissionRevision, Target, User,
                      VerificationRecord, utcnow)
from ..security import aware, current_user, has_perm, require
from ..services import audit, institution_user_ids, kpt_reviewer_ids, notify, send_email, setting_bool

router = APIRouter(prefix="/api")

STATUS_LABEL = {S_NOT_STARTED: "Belum diisi", S_DRAFT: "Draf", S_SUBMITTED: "Menunggu semakan",
                S_RETURNED: "Perlu pembetulan", S_VERIFIED: "Disahkan", S_NOT_APPLICABLE: "Tidak berkenaan"}

ALLOWED_EXT = {".pdf": "application/pdf", ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
               ".csv": "text/csv", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
               ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


def _iso(dt):
    return aware(dt).isoformat() if dt else None


def _name(db: Session, uid: Optional[int]) -> Optional[str]:
    u = db.get(User, uid) if uid else None
    return u.name if u else None


def kpi_dict(k: Kpi, targets: dict[int, Target]) -> dict:
    c = cfg(k)
    return {"id": k.id, "code": k.code, "teras": k.teras, "teras_name": TERAS.get(k.teras), "os_code": k.os_code,
            "os_name": k.os_name, "title": k.title, "indicator": k.indicator, "definition": k.definition,
            "outcome_2030": k.outcome_2030, "measurement": k.measurement, "numerator_label": k.numerator_label,
            "denominator_label": k.denominator_label, "data_owner": k.data_owner, "unit": k.unit,
            "aggregation": k.aggregation, "subset_ratio": k.subset_ratio, "itemised": k.itemised,
            "formula_status": k.formula_status, "source_ref": k.source_ref, "confirmation_notes": notes(k),
            "attestations": c.get("attestations") or [], "items_schema": c.get("items_schema"),
            "applicable_categories": c.get("applicable_categories"), "index_scale": c.get("index_scale"),
            "excellence_threshold": c.get("excellence_threshold"), "cumulative_target": c.get("cumulative_target"),
            "targets": {str(y): target_info(targets.get(y)) for y in YEARS}}


def _targets_by_kpi(db: Session) -> dict[int, dict[int, Target]]:
    out: dict[int, dict[int, Target]] = {}
    for t in db.scalars(select(Target)):
        out.setdefault(t.kpi_id, {})[t.year] = t
    return out


@router.get("/kpis")
def list_kpis(u: User = Depends(current_user), db: Session = Depends(get_db)):
    tb = _targets_by_kpi(db)
    return [kpi_dict(k, tb.get(k.id, {})) for k in db.scalars(select(Kpi).order_by(Kpi.sort_order, Kpi.id))]


@router.get("/periods")
def list_periods(u: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{"year": p.year, "status": p.status, "opens_on": p.opens_on, "closes_on": p.closes_on, "note": p.note}
            for p in db.scalars(select(ReportingPeriod).order_by(ReportingPeriod.year))]


def _period_open(db: Session, year: int) -> bool:
    p = db.scalar(select(ReportingPeriod).where(ReportingPeriod.year == year))
    return bool(p and p.status == "OPEN")


# ------------------------------------------------------------------ serialisation
def evidence_dict(db: Session, e: EvidenceFile) -> dict:
    return {"id": e.id, "name": e.original_name, "content_type": e.content_type, "size": e.size_bytes,
            "sha256": e.sha256, "revision": e.revision, "uploaded_by": _name(db, e.uploaded_by),
            "uploaded_at": _iso(e.uploaded_at), "locked": e.locked, "withdrawn": e.withdrawn_at is not None,
            "previewable": e.content_type in ("application/pdf", "image/png", "image/jpeg")}


def submission_dict(db: Session, s: Submission, k: Kpi, inst: Institution, *, full: bool = False) -> dict:
    t = db.scalar(select(Target).where(Target.kpi_id == k.id, Target.year == s.year))
    tinfo = target_info(t)
    it = institution_targets(db, inst.id, s.year).get(k.id)
    details = json.loads(s.details_json or "{}")
    d = {"id": s.id, "institution": {"id": inst.id, "code": inst.code, "name": inst.name, "category": inst.category},
         "kpi": {"id": k.id, "code": k.code, "title": k.title, "teras": k.teras, "unit": k.unit},
         "year": s.year, "status": s.status, "status_label": STATUS_LABEL.get(s.status, s.status),
         "numerator": s.numerator, "denominator": s.denominator, "value": s.value, "index_score": s.index_score,
         "index_excellent": s.index_excellent, "items": details.get("items") or [],
         "attestations": details.get("attestations") or [], "note": s.evidence_note, "review_note": s.review_note,
         "revision": s.revision, "target": tinfo, "institution_target": it,
         "comparison": institution_value(k, s, tinfo, it), "updated_at": _iso(s.updated_at),
         "submitted_at": _iso(s.submitted_at), "reviewed_at": _iso(s.reviewed_at),
         "reviewed_by": _name(db, s.reviewed_by), "submitted_by": _name(db, s.last_submitted_by)}
    if full:
        d["evidence"] = [evidence_dict(db, e) for e in db.scalars(
            select(EvidenceFile).where(EvidenceFile.submission_id == s.id).order_by(EvidenceFile.uploaded_at))]
        d["revisions"] = [{"revision": r.revision, "action": r.action, "status": r.status_after,
                           "status_label": STATUS_LABEL.get(r.status_after, r.status_after), "comment": r.comment,
                           "actor": _name(db, r.actor_id), "at": _iso(r.at), "snapshot": json.loads(r.snapshot_json)}
                          for r in db.scalars(select(SubmissionRevision).where(SubmissionRevision.submission_id == s.id)
                                              .order_by(SubmissionRevision.at, SubmissionRevision.id))]
        d["verification_history"] = [{"decision": v.decision, "comment": v.comment, "reviewer": _name(db, v.reviewer_id),
                                      "at": _iso(v.at), "revision": v.revision, "value": v.value_at_decision}
                                     for v in db.scalars(select(VerificationRecord).where(
                                         VerificationRecord.submission_id == s.id).order_by(VerificationRecord.at))]
    return d


def _snapshot(db: Session, s: Submission, action: str, actor: User, comment: Optional[str] = None) -> None:
    ev = [e.id for e in db.scalars(select(EvidenceFile).where(EvidenceFile.submission_id == s.id,
                                                              EvidenceFile.withdrawn_at.is_(None)))]
    snap = {"numerator": s.numerator, "denominator": s.denominator, "value": s.value, "index_score": s.index_score,
            "index_excellent": s.index_excellent, "details": json.loads(s.details_json or "{}"),
            "note": s.evidence_note, "evidence_ids": ev}
    db.add(SubmissionRevision(submission_id=s.id, revision=s.revision, action=action, status_after=s.status,
                              snapshot_json=json.dumps(snap, ensure_ascii=False), comment=comment, actor_id=actor.id))


def _load(db: Session, sid: int, user: User) -> tuple[Submission, Kpi, Institution]:
    s = db.get(Submission, sid)
    if not s:
        raise HTTPException(404, "Rekod laporan tidak ditemui.")
    if user.role == ROLE_IPT:
        if s.institution_id != user.institution_id:
            raise HTTPException(404, "Rekod laporan tidak ditemui.")  # do not reveal other institutions' records
    elif not has_perm(user, "submissions.view_all"):
        raise HTTPException(403, "Anda tidak mempunyai kebenaran untuk melihat rekod ini.")
    return s, db.get(Kpi, s.kpi_id), db.get(Institution, s.institution_id)


# ------------------------------------------------------------------ IPT portal
@router.get("/ipt/overview")
def ipt_overview(year: int, u: User = Depends(require("ipt.report")), db: Session = Depends(get_db)):
    if year not in YEARS:
        raise HTTPException(422, "Tahun pelaporan mesti 2026–2030.")
    inst = db.get(Institution, u.institution_id)
    kpis = list(db.scalars(select(Kpi).order_by(Kpi.sort_order, Kpi.id)))
    tb = _targets_by_kpi(db)
    subs = {s.kpi_id: s for s in db.scalars(select(Submission).where(Submission.institution_id == inst.id,
                                                                    Submission.year == year))}
    counts = {k: 0 for k in STATUS_LABEL}
    teras_cards = {t: {"teras": t, "name": n, "kpis": []} for t, n in TERAS.items()}
    for k in kpis:
        t = tb.get(k.id, {}).get(year)
        ok, reason = applicability(k, inst, t)
        s = subs.get(k.id)
        st = s.status if s else (S_NOT_STARTED if ok else S_NOT_APPLICABLE)
        if not ok and not s:
            st = S_NOT_APPLICABLE
        counts[st] += 1
        teras_cards[k.teras]["kpis"].append({"id": k.id, "code": k.code, "title": k.title, "unit": k.unit,
                                             "status": st, "status_label": STATUS_LABEL[st], "value": s.value if s else None,
                                             "target": target_info(t), "na_reason": reason})
    applicable = len(kpis) - counts[S_NOT_APPLICABLE]
    sent = counts[S_SUBMITTED] + counts[S_VERIFIED]
    for card in teras_cards.values():
        ks = [x for x in card["kpis"] if x["status"] != S_NOT_APPLICABLE]
        card["applicable"] = len(ks)
        card["sent"] = sum(1 for x in ks if x["status"] in (S_SUBMITTED, S_VERIFIED))
        card["verified"] = sum(1 for x in ks if x["status"] == S_VERIFIED)
        card["returned"] = sum(1 for x in ks if x["status"] == S_RETURNED)
    return {"institution": {"id": inst.id, "code": inst.code, "name": inst.name, "category": inst.category},
            "year": year, "period_open": _period_open(db, year), "total_kpis": len(kpis), "applicable": applicable,
            "counts": counts, "completion_pct": round(100.0 * sent / applicable, 1) if applicable else None,
            "teras": list(teras_cards.values())}


@router.get("/ipt/form/{kpi_id}")
def ipt_form(kpi_id: int, year: int, u: User = Depends(require("ipt.report")), db: Session = Depends(get_db)):
    k = db.get(Kpi, kpi_id)
    if not k or year not in YEARS:
        raise HTTPException(404, "KPI atau tahun tidak sah.")
    inst = db.get(Institution, u.institution_id)
    tb = _targets_by_kpi(db).get(k.id, {})
    ok, reason = applicability(k, inst, tb.get(year))
    s = db.scalar(select(Submission).where(Submission.institution_id == inst.id, Submission.kpi_id == k.id,
                                           Submission.year == year))
    return {"kpi": kpi_dict(k, tb), "institution": {"id": inst.id, "code": inst.code, "name": inst.name,
                                                    "category": inst.category},
            "year": year, "applicable": ok, "na_reason": reason, "period_open": _period_open(db, year),
            "evidence_required": setting_bool(db, "evidence_required_on_submit"),
            "institution_target": institution_targets(db, inst.id, year).get(k.id),
            "submission": submission_dict(db, s, k, inst, full=True) if s else None,
            "editable": ok and _period_open(db, year) and (s is None or s.status in (S_DRAFT, S_RETURNED))}


class SaveIn(BaseModel):
    kpi_id: int
    year: int
    numerator: Optional[Any] = None
    denominator: Optional[Any] = None
    index_score: Optional[Any] = None
    index_excellent: Optional[bool] = None
    items: Optional[list] = None
    attestations: Optional[list] = None
    note: Optional[str] = Field(default="", max_length=4000)


@router.put("/ipt/submissions")
def save_draft(req: SaveIn, request: Request, u: User = Depends(require("ipt.report")), db: Session = Depends(get_db)):
    k = db.get(Kpi, req.kpi_id)
    if not k or req.year not in YEARS:
        raise HTTPException(404, "KPI atau tahun tidak sah.")
    if not _period_open(db, req.year):
        raise HTTPException(409, f"Tempoh pelaporan {req.year} tidak dibuka.")
    inst = db.get(Institution, u.institution_id)
    t = db.scalar(select(Target).where(Target.kpi_id == k.id, Target.year == req.year))
    ok, reason = applicability(k, inst, t)
    if not ok:
        raise HTTPException(409, reason)
    s = db.scalar(select(Submission).where(Submission.institution_id == inst.id, Submission.kpi_id == k.id,
                                           Submission.year == req.year))
    if s and s.status in (S_SUBMITTED, S_VERIFIED):
        raise HTTPException(409, "Rekod telah dihantar/disahkan dan tidak boleh disunting kecuali dipulangkan oleh KPT.")
    m = measure(k, req.model_dump(), final=False)
    if s is None:
        s = Submission(institution_id=inst.id, kpi_id=k.id, year=req.year, status=S_DRAFT, submitted_by=u.id,
                       evidence_note="", review_note="", revision=0)
        db.add(s)
    s.numerator, s.denominator, s.value = m.numerator, m.denominator, m.value
    s.index_score, s.index_excellent = m.index_score, m.index_excellent
    s.details_json = json.dumps(m.details, ensure_ascii=False)
    s.evidence_note = (req.note or "").strip()
    s.updated_at = utcnow().replace(tzinfo=None)
    s.updated_by = u.id
    db.flush()
    _snapshot(db, s, "SAVE_DRAFT", u)
    audit(db, u, "submission_saved", f"submission:{s.id}", request, kpi=k.code, year=s.year)
    db.commit()
    return {"submission": submission_dict(db, s, k, inst, full=True), "warnings": m.warnings,
            "complete": m.complete, "message": "Draf disimpan."}


@router.post("/ipt/submissions/{sid}/submit")
def submit(sid: int, request: Request, u: User = Depends(require("ipt.report")), db: Session = Depends(get_db)):
    s, k, inst = _load(db, sid, u)
    if s.status not in (S_DRAFT, S_RETURNED):
        raise HTTPException(409, "Status rekod tidak membenarkan penghantaran.")
    if not _period_open(db, s.year):
        raise HTTPException(409, f"Tempoh pelaporan {s.year} tidak dibuka.")
    t = db.scalar(select(Target).where(Target.kpi_id == k.id, Target.year == s.year))
    ok, reason = applicability(k, inst, t)
    if not ok:
        raise HTTPException(409, reason)
    details = json.loads(s.details_json or "{}")
    payload = {"numerator": s.numerator, "denominator": s.denominator, "index_score": s.index_score,
               "index_excellent": s.index_excellent, "items": details.get("items"),
               "attestations": details.get("attestations")}
    m = measure(k, payload, final=True)
    active_ev = list(db.scalars(select(EvidenceFile).where(EvidenceFile.submission_id == s.id,
                                                           EvidenceFile.withdrawn_at.is_(None))))
    if setting_bool(db, "evidence_required_on_submit") and not active_ev:
        raise HTTPException(422, "Sekurang-kurangnya satu dokumen sokongan wajib dimuat naik sebelum dihantar.")
    was_returned = s.status == S_RETURNED
    s.numerator, s.denominator, s.value = m.numerator, m.denominator, m.value
    s.index_score, s.index_excellent = m.index_score, m.index_excellent
    s.revision += 1
    s.status = S_SUBMITTED
    s.submitted_at = utcnow()
    s.last_submitted_by = u.id
    s.updated_at = utcnow().replace(tzinfo=None)
    for e in active_ev:
        e.locked = True
    _snapshot(db, s, "RESUBMIT" if was_returned else "SUBMIT", u)
    audit(db, u, "submission_submitted", f"submission:{s.id}", request, kpi=k.code, year=s.year, revision=s.revision)
    notify(db, kpt_reviewer_ids(db, need_verify=True), "REPORT_SUBMITTED",
           f"Laporan KPI {'dihantar semula' if was_returned else 'dihantar'}: {k.code}",
           f"{inst.name} — {k.title} ({s.year}).", f"#/kpt/semakan/{s.id}")
    db.commit()
    return {"submission": submission_dict(db, s, k, inst, full=True),
            "message": "Laporan dihantar untuk semakan KPT."}


# ------------------------------------------------------------------ evidence
def _sniff_ok(ext: str, head: bytes) -> bool:
    if ext == ".pdf":
        return head.startswith(b"%PDF-")
    if ext == ".png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if ext in (".jpg", ".jpeg"):
        return head.startswith(b"\xff\xd8\xff")
    if ext in (".xlsx", ".docx"):
        return head.startswith(b"PK\x03\x04")
    if ext == ".csv":
        if b"\x00" in head:
            return False
        try:
            head.decode("utf-8")
        except UnicodeDecodeError:
            try:
                head.decode("cp1252")
            except UnicodeDecodeError:
                return False
        return True
    return False


def _safe_name(name: str) -> str:
    name = Path(name or "fail").name
    name = re.sub(r"[^\w.\- ()]+", "_", name, flags=re.UNICODE).strip() or "fail"
    return name[-150:]


@router.post("/ipt/submissions/{sid}/evidence", status_code=201)
async def upload_evidence(sid: int, request: Request, file: UploadFile = File(...),
                          u: User = Depends(require("ipt.report")), db: Session = Depends(get_db)):
    s, k, inst = _load(db, sid, u)
    if s.status not in (S_DRAFT, S_RETURNED):
        raise HTTPException(409, "Dokumen hanya boleh dimuat naik semasa draf atau selepas laporan dipulangkan.")
    original = _safe_name(file.filename or "")
    ext = Path(original).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(415, "Jenis fail tidak dibenarkan. Dibenarkan: PDF, XLSX, CSV, DOCX, PNG, JPG.")
    limit = settings.max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"Saiz fail melebihi had {settings.max_upload_mb} MB.")
    if not data:
        raise HTTPException(422, "Fail kosong.")
    if not _sniff_ok(ext, data[:4096]):
        raise HTTPException(415, "Kandungan fail tidak sepadan dengan jenis fail.")
    stored = f"{uuid.uuid4().hex}{ext}"
    folder = settings.evidence_dir / str(s.year)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / stored).write_bytes(data)
    e = EvidenceFile(submission_id=s.id, institution_id=inst.id, kpi_id=k.id, year=s.year, revision=s.revision + 1,
                     original_name=original, stored_name=stored, content_type=ALLOWED_EXT[ext], size_bytes=len(data),
                     sha256=hashlib.sha256(data).hexdigest(), uploaded_by=u.id)
    db.add(e)
    db.flush()
    audit(db, u, "evidence_uploaded", f"evidence:{e.id}", request, submission=s.id, name=original, sha256=e.sha256)
    db.commit()
    return evidence_dict(db, e)


@router.post("/evidence/{eid}/withdraw")
def withdraw_evidence(eid: int, request: Request, u: User = Depends(require("ipt.report")), db: Session = Depends(get_db)):
    e = db.get(EvidenceFile, eid)
    if not e or e.institution_id != u.institution_id:
        raise HTTPException(404, "Dokumen tidak ditemui.")
    s = db.get(Submission, e.submission_id)
    if e.locked or s.status not in (S_DRAFT, S_RETURNED):
        raise HTTPException(409, "Dokumen yang telah dihantar bersama laporan dikekalkan sebagai rekod sejarah.")
    if e.withdrawn_at:
        raise HTTPException(409, "Dokumen telah ditarik balik.")
    e.withdrawn_at, e.withdrawn_by = utcnow(), u.id
    audit(db, u, "evidence_withdrawn", f"evidence:{e.id}", request)
    db.commit()
    return {"ok": True}


@router.get("/evidence/{eid}/download")
def download_evidence(eid: int, request: Request, inline: bool = False, u: User = Depends(current_user),
                      db: Session = Depends(get_db)):
    e = db.get(EvidenceFile, eid)
    if not e:
        raise HTTPException(404, "Dokumen tidak ditemui.")
    if u.role == ROLE_IPT:
        if e.institution_id != u.institution_id:
            raise HTTPException(404, "Dokumen tidak ditemui.")
    elif not has_perm(u, "submissions.view_all"):
        raise HTTPException(403, "Anda tidak mempunyai kebenaran untuk dokumen sokongan.")
    path = settings.evidence_dir / str(e.year) / e.stored_name
    if not path.is_file():
        raise HTTPException(410, "Fail tidak lagi tersedia dalam storan.")
    audit(db, u, "evidence_downloaded", f"evidence:{e.id}", request)
    db.commit()
    preview = inline and e.content_type in ("application/pdf", "image/png", "image/jpeg")
    resp = FileResponse(path, media_type=e.content_type, filename=e.original_name,
                        content_disposition_type="inline" if preview else "attachment")
    # PDFs need the browser's built-in viewer (a sandboxed document cannot load it); other types are sandboxed.
    resp.headers["Content-Security-Policy"] = ("default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; object-src 'self'"
                                               if e.content_type == "application/pdf" else
                                               "sandbox; default-src 'none'; img-src 'self'; style-src 'unsafe-inline'")
    resp.headers["Cache-Control"] = "private, no-store"
    return resp


# ------------------------------------------------------------------ submissions (shared / KPT)
@router.get("/submissions")
def list_submissions(year: Optional[int] = None, status: str = "", institution_id: Optional[int] = None,
                     kpi_id: Optional[int] = None, teras: Optional[int] = None, u: User = Depends(current_user),
                     db: Session = Depends(get_db)):
    q = select(Submission)
    if u.role == ROLE_IPT:
        q = q.where(Submission.institution_id == u.institution_id)
    elif not has_perm(u, "submissions.view_all"):
        raise HTTPException(403, "Anda tidak mempunyai kebenaran untuk melihat rekod laporan.")
    elif institution_id:
        q = q.where(Submission.institution_id == institution_id)
    if year:
        q = q.where(Submission.year == year)
    if status:
        q = q.where(Submission.status == status)
    if kpi_id:
        q = q.where(Submission.kpi_id == kpi_id)
    kpis = {k.id: k for k in db.scalars(select(Kpi))}
    insts = {i.id: i for i in db.scalars(select(Institution))}
    rows = []
    for s in db.scalars(q.order_by(Submission.submitted_at.desc().nullslast(), Submission.id.desc())):
        k = kpis[s.kpi_id]
        if teras and k.teras != teras:
            continue
        rows.append(submission_dict(db, s, k, insts[s.institution_id]))
    return rows


@router.get("/submissions/{sid}")
def submission_detail(sid: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    s, k, inst = _load(db, sid, u)
    tb = _targets_by_kpi(db).get(k.id, {})
    d = submission_dict(db, s, k, inst, full=True)
    d["kpi_full"] = kpi_dict(k, tb)
    d["can_review"] = has_perm(u, "submissions.verify") and s.status == S_SUBMITTED
    d["can_reopen"] = has_perm(u, "submissions.reopen") and s.status == S_VERIFIED
    return d


class ReviewIn(BaseModel):
    decision: str
    comment: str = Field(default="", max_length=4000)


@router.post("/submissions/{sid}/review")
def review(sid: int, req: ReviewIn, request: Request, u: User = Depends(require("submissions.verify")),
           db: Session = Depends(get_db)):
    s, k, inst = _load(db, sid, u)
    if s.status != S_SUBMITTED:
        raise HTTPException(409, "Hanya laporan berstatus 'Menunggu semakan' boleh disahkan atau dipulangkan.")
    decision = req.decision.upper()
    if decision not in (S_VERIFIED, S_RETURNED):
        raise HTTPException(422, "Keputusan mesti VERIFIED atau RETURNED.")
    comment = (req.comment or "").strip()
    if decision == S_RETURNED and len(comment) < 5:
        raise HTTPException(422, "Ulasan penyemak wajib dinyatakan apabila memulangkan laporan.")
    s.status = decision
    s.reviewed_by, s.reviewed_at, s.review_note = u.id, utcnow(), comment
    db.add(VerificationRecord(submission_id=s.id, revision=s.revision, decision=decision, comment=comment or None,
                              reviewer_id=u.id, value_at_decision=s.value))
    _snapshot(db, s, "VERIFY" if decision == S_VERIFIED else "RETURN", u, comment or None)
    audit(db, u, "submission_" + decision.lower(), f"submission:{s.id}", request, kpi=k.code, year=s.year)
    label = "disahkan" if decision == S_VERIFIED else "dipulangkan untuk pembetulan"
    recipients = institution_user_ids(db, inst.id)
    notify(db, recipients, "REPORT_" + decision, f"Laporan {k.code} ({s.year}) {label}",
           comment or f"Laporan {k.title} telah {label}.", f"#/ipt/kpi/{k.id}?tahun={s.year}")
    for uid in recipients:
        ru = db.get(User, uid)
        send_email(db, ru.email, f"PSKG Monitor 2030: Laporan {k.code} {label}",
                   f"Salam {ru.name},\n\nLaporan {k.code} — {k.title} bagi tahun {s.year} telah {label} oleh KPT."
                   + (f"\nUlasan: {comment}" if comment else "") + "\n", kind="REPORT_" + decision)
    db.commit()
    return {"status": s.status, "status_label": STATUS_LABEL[s.status]}


class ReopenIn(BaseModel):
    comment: str = Field(max_length=4000)


@router.post("/submissions/{sid}/reopen")
def reopen(sid: int, req: ReopenIn, request: Request, u: User = Depends(require("submissions.reopen")),
           db: Session = Depends(get_db)):
    """Controlled, audited re-opening of a VERIFIED report (never a silent edit)."""
    s, k, inst = _load(db, sid, u)
    if s.status != S_VERIFIED:
        raise HTTPException(409, "Hanya laporan yang disahkan boleh dibuka semula.")
    comment = (req.comment or "").strip()
    if len(comment) < 10:
        raise HTTPException(422, "Nyatakan justifikasi pembukaan semula (sekurang-kurangnya 10 aksara).")
    s.status = S_RETURNED
    s.review_note = comment
    s.reviewed_by, s.reviewed_at = u.id, utcnow()
    db.add(VerificationRecord(submission_id=s.id, revision=s.revision, decision="REOPENED", comment=comment,
                              reviewer_id=u.id, value_at_decision=s.value))
    _snapshot(db, s, "REOPEN", u, comment)
    audit(db, u, "submission_reopened", f"submission:{s.id}", request, comment=comment)
    notify(db, institution_user_ids(db, inst.id), "REPORT_RETURNED", f"Laporan {k.code} ({s.year}) dibuka semula",
           comment, f"#/ipt/kpi/{k.id}?tahun={s.year}")
    db.commit()
    return {"status": s.status}
