# Existing-code audit: Pilot V2B → MVP (Phase 1)

Inputs reviewed: `pskg_monitor_v2b 2.zip` (all files), `PSKG_Monitor_2030_Prototaip.html`, `PSKG_final_KPI.pptx`
(the text of all 44 slides was extracted; slides 14, 18, 22, 26, 30 and 33 were also rendered and checked visually),
and the existing `pskg_dev.db`.

## 1. What V2B already did well (kept)

| Feature | Where it lives now |
|---|---|
| FastAPI + SQLAlchemy 2 structure; SQLite for development and PostgreSQL through Docker | Kept: `app/db.py`, `docker-compose.yml` |
| Argon2 password hashing (`pwdlib`) | Kept: `app/security.py` |
| Opaque session tokens stored only as SHA-256 digests | Kept. The token now travels in an HttpOnly cookie instead of `sessionStorage`. |
| Role and institution segregation; IPT users see only their own institution | Kept and extended to every endpoint |
| `draft → submitted → approved/returned` workflow with a uniqueness constraint on institution + KPI + year | Kept (statuses renamed to `DRAFT/SUBMITTED/VERIFIED/RETURNED`) |
| Pooled national percentage (Σnumerator ÷ Σdenominator) and "approved only" dashboard | Kept: `app/analytics.py` |
| KPI targets for slides 14–30 | Kept and checked against the slides |
| Table names and existing data (1 pending institution, 1 pending user, 20 KPIs, 100 targets) | Kept. Upgraded by migration `0002`. The pending user becomes a *Menunggu Kelulusan* application. |

## 2. Defects and gaps found in V2B

| # | Finding | Fix in MVP |
|---|---|---|
| 1 | Schema created with `Base.metadata.create_all()` at start-up; no migrations; `@app.on_event` is deprecated | Alembic migrations `0001`/`0002` and a lifespan handler. The upgrade of a V2B database is tested. |
| 2 | No login rate limiting. The "dummy hash" comment was never implemented, so an unknown e-mail returned faster than a known one. | Per-account and per-IP lockout, constant-time verification using a dummy hash, generic error messages |
| 3 | Approval required two separate admin steps (institution, then user) and only `admin` could approve | A single **Luluskan/Tolak Permohonan** action for Penyelaras KPT, with officer, timestamp and reason recorded |
| 4 | Registration collected only 5 fields; no category, address, state, position, department or phone; no confirm-password | Full Sections A–C, duplicate checks, password policy, selection from the institution directory |
| 5 | No KPT pre-registration, activation, password reset or status check | Implemented with single-use, expiring tokens of which only the hash is stored |
| 6 | `numerator` NOT NULL, so incomplete drafts were impossible; `float` input allowed fractional counts | Nullable values in drafts, integer validation, checks for both drafts and final submission |
| 7 | `review_note` was overwritten on every decision; no revision history | `submission_revisions` and `verification_history` |
| 8 | Evidence was a free-text note only | Secure upload module (`evidence_files`) |
| 9 | KPI 17 targets were stored as NULL for 2026–2029 and the KPI was treated as an ordinary percentage | Slide 26 checked visually: 50% and 100% are *index-development milestones*, followed by 60/70/75%. The KPI now has a special index type, national milestones, IPTA-only applicability and a 4–5 "cemerlang" threshold (slide 33). |
| 10 | KPIs had no official codes (T1/OS1/A …), numerator or denominator labels, or data owners | Full KPI dictionary transcribed from the slides (`app/kpi_catalogue.py`) |
| 11 | The IPT dashboard compared a single institution's count with the **national** count target, effectively making it a quota | National count targets are never used as IPT quotas. Optional KPT-set institution targets are available. |
| 12 | No reporting coverage against the population of institutions; no completeness matrix | Coverage on every aggregate; institution × KPI matrix; official population reference (slide 38) |
| 13 | `audit_log.actor_id` NOT NULL, so anonymous events (registration, failed login) could not be logged; no IP or detail recorded | Nullable actor, IP address and JSON detail |
| 14 | Frontend used inline `onclick`, `prompt()` and `confirm()`; no CSP; token held in `sessionStorage` | Event delegation, Bootstrap modals, strict CSP, HttpOnly cookie, CSRF header |
| 15 | No notifications, reporting periods, exports, executive charts or admin configuration | Implemented |
| 16 | The logout endpoint sliced the `Authorization` header directly, which breaks with cookies | Session-object based logout |

## 3. Prototype (HTML) reuse

Reused from the prototype:

- the navy/teal/grey/white palette and sidebar navigation;
- stat cards, the five Teras cards, the KPI register table and the target timeline;
- the form layout with its definition panel;
- the review list and the CSV export idea.

Replaced:

- `localStorage` storage, simulated `seed()` values and the role selector are replaced by real API calls, the
  database and server-side authentication;
- the prototype's `[null,null,50,75,100]` KPI 17 targets and its unweighted "average % of target" by Teras are
  replaced by source-verified targets and non-averaged Teras breakdowns (met / below / no data).

## 4. Remaining limitations (honest list)

- **Screenshots.** The prompt mentions login and registration screenshots, but none were included in the upload.
  The pages follow the described direction (dark navy header, light-grey background, white centred card, blue
  buttons, pilot notice) and the V2B layout. They can be adjusted once the screenshots are shared.
- **Rate limiting** uses database ledgers. It works across workers, but it is not a substitute for
  gateway or WAF rate limiting in production.
- **No MFA or SSO**, and no virus scanning of uploads. The PDF export uses a simple tabular layout.
- **Applicant identity.** Self-registration cannot prove an applicant's identity. Penyelaras KPT must verify it
  independently; the review screen reminds them and flags mismatched e-mail domains.
- **No external integrations.** There is no integration with a national IPT registry, MyGRAD or any other
  system of record.
