# PSKG Monitor 2030 — MVP

**Sistem Pemantauan Prestasi, Pelaporan dan Analitik Kebolehpasaran Graduan Peringkat Nasional**
Pelan Strategik Kebolehpasaran Graduan (PSKG) 2026–2030 · Penyeliaan: Dr Bibi, BJIK, ICAN UiTM

This is a working, database-driven web application, not a mock-up. It extends the original *Pilot V2B*
FastAPI project in place. All V2B data is kept and upgraded automatically through database migrations.

> **Status:** pilot MVP. This is **not** an accredited or production-authorised KPT system. KPI formulas
> are marked **DRAF** until KPT formally confirms them. See [`docs/PENGESAHAN_KPT.md`](docs/PENGESAHAN_KPT.md).
> Use synthetic data only unless KPT has authorised you to use real institutional data.

---

## 1. Quick start on Windows (PowerShell, no Docker, no XAMPP)

```powershell
cd C:\Users\User\Documents\pskg_monitor_v2b

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

# 1) Create / upgrade the database (also happens automatically when the server starts)
python -m scripts.migrate

# 2) Create the FIRST Pentadbir KPT account (run once; NOT needed on every start-up)
python -m scripts.bootstrap_admin

# 3) (Optional) Load fictitious demonstration data and print a random demo password
python -m scripts.seed_demo --generate

# 4) Start the server
python -m uvicorn app.main:app --reload
```

Open **http://localhost:8000** to see the login page (*Log Masuk*). The API documentation is at
**http://localhost:8000/api/docs**.

### macOS / Linux

```bash
cd ~/PSKG/pskg_monitor_v2b
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt
python -m scripts.bootstrap_admin
python -m uvicorn app.main:app --reload
```

### VS Code

Open the folder, run **Python: Select Interpreter** and choose `.venv`. Then use **Run and Debug** with one
of the configurations in `.vscode/launch.json`:

- PSKG Monitor 2030 (Uvicorn)
- Cipta Pentadbir KPT pertama
- Data demo sintetik
- Ujian automatik

### Troubleshooting on Windows

| Problem | Fix |
|---|---|
| `Activate.ps1 cannot be loaded because running scripts is disabled` | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then activate again. Or use `.\.venv\Scripts\activate.bat` in Command Prompt. |
| `'python' is not recognized` | Install Python 3.11–3.13 from python.org and tick **Add python.exe to PATH**. Alternatively, use `py -3.12` instead of `python`. |
| `Address already in use` / `[WinError 10048]` | Port 8000 is busy. Use `python -m uvicorn app.main:app --reload --port 8001` and set `PUBLIC_URL=http://localhost:8001` in `.env`. |
| `ModuleNotFoundError: app` | Run commands from the project folder (the one that contains `app\`), with the virtual environment activated. |
| `database is locked` | Close other programs that have `pskg_dev.db` open (for example DB Browser for SQLite). |
| The page loads without styling, or the scripts do not run | Press Ctrl+F5. The server forces the correct JavaScript MIME type even when the Windows registry maps `.js` wrongly. |
| `argon2` / `cffi` build error during `pip install` | Upgrade pip first (`python -m pip install --upgrade pip`), then install again. Wheels are available for Python 3.11–3.13. |
| Activation or reset links point to the wrong port | Set `PUBLIC_URL` in `.env`. |

### Optional: Docker with PostgreSQL

Create a `.env` file containing `POSTGRES_PASSWORD=<long random password>`, then run `docker compose up --build -d`
and `docker compose exec web python -m scripts.bootstrap_admin`.

---

## 2. Trying the two mandatory account-registration methods

**Method 1: IPT self-registration, then KPT approval**

1. On the login page, click **Daftar institusi baharu**.
2. Complete Sections A–C and click **Hantar permohonan**.
3. The applicant sees a **No. Permohonan** and a **Kod Semakan**. The status is *Menunggu Kelulusan*.
4. Logging in now is refused with the message "Akaun anda masih menunggu kelulusan Penyelaras KPT".
   This message appears only when the password is correct, so it does not reveal whether an account exists.
5. A Penyelaras KPT opens **Permohonan Akaun IPT**, clicks **Lihat Permohonan**, reviews the details and the
   system's duplicate checks, then clicks **Luluskan Permohonan** (or **Tolak Permohonan**, which requires a reason).
6. The applicant can now log in. **Semak status permohonan** shows *Diluluskan*.

**Method 2: KPT pre-registration, then secure activation**

1. A Penyelaras KPT opens **Pra-Daftar Akaun IPT**.
2. They select an existing institution or register a new one, enter the designated officer's details and click
   **Pra-daftar & hantar jemputan**.
3. The system creates a single-use activation link that expires after 72 hours. Only the SHA-256 hash of the
   token is stored. No password is ever generated or e-mailed.
4. The officer opens the link, confirms their details, sets a password and logs in. No second KPT approval is needed.
5. **Senarai Akaun IPT** and **Status Pengaktifan Akaun** show the invitation status. From there a Penyelaras KPT
   can resend an expired invitation, deactivate or reactivate an account, or change its institution.

**E-mail delivery.** If `SMTP_HOST` is not set, e-mails are **not** sent. They are stored as clearly labelled
development previews under **Pratonton Emel (Dev)**. The pre-registration screen also shows the activation link,
marked *PRATONTON PEMBANGUNAN*. The system never claims an e-mail was delivered when it was not. Set the `SMTP_*`
variables in `.env` to send real e-mails.

---

## 3. What is in the system

| Area | Modules |
|---|---|
| Public | Log Masuk, Daftar institusi baharu, Semak status permohonan, Lupa kata laluan, Pengaktifan akaun |
| **Portal Pelaporan IPT** (Penyelaras IPT) | Dashboard IPT (20 KPI, status counts, completion %, five Teras cards) · Borang KPI dinamik · Dokumen sokongan · Rekod Disahkan · Laporan |
| **Portal Pemantauan KPT** (Penyelaras KPT) | Dashboard Pemantauan · Status Pelaporan IPT (institution × KPI matrix) · Semakan & Pengesahan · Prestasi Nasional · Permohonan Akaun IPT · Pra-Daftar Akaun IPT · Senarai Akaun IPT · Status Pengaktifan Akaun · Sejarah Kelulusan · Direktori Institusi |
| **Dashboard Eksekutif** (Pengurusan Tertinggi, read-only) | Summary cards · five Teras cards · target vs actual · gap to target · 2026–2030 trend · institution comparison · reporting coverage · Teras breakdown · detailed KPI table · filters for year, Teras, KPI, institution and category |
| **Pentadbiran** (Pentadbir KPT) | Pengguna & Peranan · Tempoh Pelaporan · KPI & Sasaran (audited target changes, national index milestones, optional institution targets) · Log Audit · Tetapan Sistem (configurable pilot notice) |
| Reports | Laporan Prestasi IPT, KPI Nasional, Mengikut Teras, Sasaran vs Pencapaian, Status Pelaporan, Pengesahan KPT, Trend Tahunan, each in **CSV, XLSX and PDF** |

### Roles and permissions (enforced on the server)

| Role (`users.role`) | Can do |
|---|---|
| `ipt`: Penyelaras IPT | Report KPIs for **its own institution only**: drafts, evidence, submission and resubmission, institutional reports |
| `kpt`: Penyelaras KPT | Approve or reject applications, pre-register IPT accounts, manage IPT accounts, monitoring, verify or return reports (when `can_verify`), national reports |
| `admin`: Pentadbir KPT | Everything a Penyelaras KPT can do, plus users and roles, reporting periods, KPI definitions and targets, milestones, audit log, settings, and audited re-opening of verified reports |
| `executive`: Pengurusan Tertinggi | Read-only executive dashboard and national reports |

V2B role names are migrated automatically: `reviewer` becomes `kpt` and `viewer` becomes `executive`.

### Reporting workflow

`NOT_STARTED → DRAFT → SUBMITTED → VERIFIED`, or `SUBMITTED → RETURNED → (correction) → SUBMITTED`.

- Drafts may be incomplete. Submitting requires complete, valid values, all eligibility confirmations and at least
  one supporting document (this last rule can be configured).
- A submitted record is locked until KPT returns it. A verified record is locked permanently. Only a Pentadbir KPT
  can re-open one, must give a justification, and the action is recorded in the audit log.
- Every save, submit, return, verify and re-open writes a full snapshot to `submission_revisions`. Every KPT decision
  is written to `verification_history` with the reviewer, timestamp, revision and value.
- Supporting documents (PDF, XLSX, CSV, DOCX, PNG, JPG; 10 MB each by default) are checked by extension **and** by
  file signature. They are stored under random names in `storage/evidence/<year>/`, outside the web root, and can
  only be downloaded through an authorised endpoint. Documents that were part of a submitted revision cannot be
  withdrawn.

### Calculations and aggregation (server-side only)

- **Percentage KPIs:** `Pencapaian (%) = A ÷ B × 100`. A and B must be whole numbers ≥ 0 and B must be greater than 0.
  For KPIs where A is a subset of B, A cannot exceed B. For the two KPIs whose official formula divides graduates by
  enrolment, the system warns instead of blocking.
- **Count KPIs:** whole numbers ≥ 0. National count targets are **never** applied as quotas for each IPT.
  Institution targets apply only if KPT sets them explicitly.
- **Itemised counts** (T3/OS1/A intellectual property, T5/OS1/A Quintuple Helix): every item carries a unique
  reference, so duplicates across institutions are removed from the national figure.
- **T4/OS2/B Indeks Kepuasan Majikan:** 2026 and 2027 are *national index-development milestones*
  (50% and 100% "Selesai Pembangunan Indeks"). KPT records these, and they are never treated as satisfaction scores.
  From 2028, each IPTA reports its index score. A score of 4 or more counts as "cemerlang" (slide 33: score 4–5).
  The national figure is the percentage of reporting IPTA rated cemerlang.
- **National figures** use **verified records only**. Percentages are pooled as `100 × ΣA ÷ ΣB` and are never an
  average of institutional percentages. Missing or unverified data is never treated as zero, and reporting coverage
  is always shown. Charts that combine percentage and count KPIs use an explicitly labelled normalisation:
  achievement ÷ target × 100.

---

## 4. Architecture

```
Browser (Bahasa Melayu SPA: HTML + Bootstrap 5 + Chart.js, vendored locally; strict CSP, no inline scripts)
   │  same-origin HTTPS in deployment · HttpOnly SameSite=Strict session cookie · CSRF header check
FastAPI (app/main.py) ── routers: public · accounts · reporting · dashboards · reports · admin
   │  SQLAlchemy 2 · server-side validation & calculation (app/measurement.py) · aggregation (app/analytics.py)
SQLite (local MVP)  or  PostgreSQL (deployment) ── schema managed by Alembic migrations (migrations/)
storage/evidence/   ── supporting documents (not publicly served)
```

**Database tables:** `institutions`, `users`, `login_sessions`, `login_attempts`, `rate_events`,
`registration_applications`, `account_invitations`, `account_approvals`, `notifications`, `email_outbox`, `kpis`
(the KPI dictionary), `targets`, `institution_targets`, `reporting_periods`, `submissions` (the KPI measurements),
`submission_revisions`, `verification_history`, `evidence_files`, `kpi_milestones`, `audit_log` and `app_settings`.
Foreign keys, uniqueness constraints (institution + KPI + year, institution code and name, user e-mail) and indexes
are all defined in the migrations.

**Migrations.** `0001_v2b_baseline` reproduces the V2B schema, or skips it if those tables already exist.
`0002_mvp_schema` upgrades the schema **without deleting data**:

- statuses and roles are translated to the new names;
- pending V2B registrations become *Menunggu Kelulusan* applications;
- KPIs gain their official codes and labels;
- the slide-26 targets for the Employer Satisfaction Index are filled in.

Migrations run automatically when the server starts (`AUTO_MIGRATE=true`), or manually with
`python -m scripts.migrate`.

## 5. Security controls implemented

- Argon2 password hashing and a password policy (at least 12 characters with upper-case, lower-case and a digit).
  The server never stores or sends plaintext passwords.
- Opaque session tokens. Only their SHA-256 digests are stored. The token travels in an HttpOnly, SameSite=Strict
  cookie and is never readable by JavaScript.
- Login rate limiting: 5 failures per account in 15 minutes, plus a per-IP limit. Public forms are also throttled.
- Login errors are generic and do not reveal whether an account exists. Password reset gives the same response
  for any e-mail address.
- Role-based and institution-based authorisation on **every** endpoint. Approving or verifying is impossible
  through direct API calls without the right permission. This is covered by automated tests.
- CSRF protection through a required custom header. Security headers are set: CSP `script-src 'self'`, nosniff,
  frame and referrer policies, and HSTS when `COOKIE_SECURE=true`.
- Safe file handling: allow-list, signature check, size limit, random storage names, path-traversal-safe names,
  restricted download and sandbox CSP.
- Audit log for logins, account decisions, submissions, reviews, evidence, exports, target changes and settings.
- No secrets in the source code. Configuration comes from `.env`, as shown in `.env.example`.

**These controls have not been through a formal security audit or penetration test.** Before any live use,
complete the deployment gates in `docs/PENGESAHAN_KPT.md` §C (HTTPS, backups, MFA/SSO, KPT authorisation and so on).

## 6. Tests

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

The suite has 69 automated tests that cover:

- account registration, approval, rejection, duplicates, pre-registration, activation, expiry, password reset,
  deactivation and institution isolation;
- KPI catalogue and targets, calculations, validation, the KPI 17 special case, drafts, submission, correction
  and resubmission, and evidence;
- the verification workflow and unauthorised attempts to verify;
- the dashboard aggregation rules (verified-only, pooled percentages, de-duplicated counts, completeness, missing
  data never treated as zero, year filters);
- end-to-end scenarios A–D;
- security controls, exports, and the migration of a V2B database.

The suite passes on SQLite and on PostgreSQL 16. To use PostgreSQL, set `TEST_DATABASE_URL` to an empty database.

## 7. Project layout

```
app/
  main.py            FastAPI app, security middleware, routers, static SPA
  config.py          settings from .env (no secrets in code)
  db.py, models.py   SQLAlchemy engine and models
  kpi_catalogue.py   official 20-KPI dictionary transcribed from PSKG_final_KPI.pptx
  measurement.py     validation and calculation for each KPI type
  analytics.py       national/institution aggregation, completeness matrix
  security.py        hashing, sessions, permissions, rate limiting
  services.py        audit, notifications, e-mail (SMTP or dev preview), settings
  routers/           public, accounts, reporting, dashboards, reports, admin
  static/            index.html, css/app.css, js/*.js, vendor/ (Bootstrap 5.3.3, Chart.js 4.4.4)
migrations/          Alembic environment + versions
scripts/             migrate, bootstrap_admin, create_staff, seed_demo
tests/               pytest suite
docs/                AUDIT.md (existing-code audit), PENGESAHAN_KPT.md (items for KPT confirmation)
storage/             uploaded evidence (created at runtime; back it up together with the database)
```
