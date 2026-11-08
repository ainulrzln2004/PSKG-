"""The migration must upgrade an existing Pilot V2B database without losing data."""
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

from app.migrate import upgrade_to_head


def _v2b_database(path: Path) -> None:
    """Re-create the exact V2B schema (as produced by Base.metadata.create_all) and legacy rows."""
    c = sqlite3.connect(path)
    c.executescript("""
    CREATE TABLE institutions (id INTEGER NOT NULL, name VARCHAR NOT NULL, code VARCHAR NOT NULL, status VARCHAR NOT NULL, PRIMARY KEY (id));
    CREATE UNIQUE INDEX ix_institutions_name ON institutions (name);
    CREATE UNIQUE INDEX ix_institutions_code ON institutions (code);
    CREATE TABLE kpis (id INTEGER NOT NULL, teras INTEGER NOT NULL, title VARCHAR NOT NULL, unit VARCHAR NOT NULL, formula_status VARCHAR NOT NULL, PRIMARY KEY (id));
    CREATE TABLE users (id INTEGER NOT NULL, email VARCHAR NOT NULL, name VARCHAR NOT NULL, password_digest VARCHAR NOT NULL, role VARCHAR NOT NULL, institution_id INTEGER, status VARCHAR NOT NULL, PRIMARY KEY (id), FOREIGN KEY(institution_id) REFERENCES institutions (id));
    CREATE UNIQUE INDEX ix_users_email ON users (email);
    CREATE TABLE targets (id INTEGER NOT NULL, kpi_id INTEGER NOT NULL, year INTEGER NOT NULL, value FLOAT, PRIMARY KEY (id), UNIQUE (kpi_id, year), FOREIGN KEY(kpi_id) REFERENCES kpis (id));
    CREATE TABLE login_sessions (id INTEGER NOT NULL, user_id INTEGER NOT NULL, token_digest VARCHAR NOT NULL, expires_at DATETIME NOT NULL, PRIMARY KEY (id), FOREIGN KEY(user_id) REFERENCES users (id));
    CREATE UNIQUE INDEX ix_login_sessions_token_digest ON login_sessions (token_digest);
    CREATE TABLE submissions (id INTEGER NOT NULL, institution_id INTEGER NOT NULL, kpi_id INTEGER NOT NULL, year INTEGER NOT NULL, numerator FLOAT NOT NULL, denominator FLOAT, evidence_note VARCHAR NOT NULL, status VARCHAR NOT NULL, submitted_by INTEGER NOT NULL, reviewed_by INTEGER, review_note VARCHAR NOT NULL, updated_at DATETIME NOT NULL, PRIMARY KEY (id), UNIQUE (institution_id, kpi_id, year), FOREIGN KEY(institution_id) REFERENCES institutions (id), FOREIGN KEY(kpi_id) REFERENCES kpis (id), FOREIGN KEY(submitted_by) REFERENCES users (id), FOREIGN KEY(reviewed_by) REFERENCES users (id));
    CREATE TABLE audit_log (id INTEGER NOT NULL, actor_id INTEGER NOT NULL, event VARCHAR NOT NULL, record VARCHAR NOT NULL, at DATETIME NOT NULL, PRIMARY KEY (id), FOREIGN KEY(actor_id) REFERENCES users (id));
    """)
    c.execute("INSERT INTO institutions VALUES (1,'Universiti Lama','LAMA','active'),(2,'Kolej Menunggu','TUNGGU','pending')")
    for kid, t, unit in [(1, 1, "percent"), (16, 4, "count"), (17, 4, "percent")]:
        c.execute("INSERT INTO kpis VALUES (?,?,?,?, 'draft')", (kid, t, f"KPI {kid}", unit))
    c.execute("INSERT INTO targets (kpi_id, year, value) VALUES (1,2026,2),(17,2026,NULL),(17,2030,75)")
    c.execute("INSERT INTO users VALUES (1,'ipt@lama.test','IPT Lama','$argon2id$fake','ipt',1,'active'),"
              "(2,'semak@kpt.test','Penyemak','$argon2id$fake','reviewer',NULL,'active'),"
              "(3,'lihat@kpt.test','Eksekutif','$argon2id$fake','viewer',NULL,'active'),"
              "(4,'baru@tunggu.test','Pemohon','$argon2id$fake','ipt',2,'pending')")
    now = datetime(2026, 5, 1).isoformat(sep=" ")
    c.execute("INSERT INTO submissions VALUES (1,1,1,2026,40,1000,'nota','approved',1,2,'',?),"
              "(2,1,16,2026,12,NULL,'','submitted',1,NULL,'',?)", (now, now))
    c.execute("INSERT INTO audit_log VALUES (1,1,'login','user:1',?)", (now,))
    c.commit()
    c.close()


def test_v2b_database_upgrade_preserves_data():
    path = Path(tempfile.mkdtemp()) / "v2b.db"
    _v2b_database(path)
    upgrade_to_head(f"sqlite:///{path.as_posix()}")
    upgrade_to_head(f"sqlite:///{path.as_posix()}")  # idempotent
    c = sqlite3.connect(path)
    assert c.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0002_mvp_schema"
    assert c.execute("SELECT id, status FROM institutions ORDER BY id").fetchall() == [(1, "ACTIVE"), (2, "PENDING")]
    roles = dict(c.execute("SELECT email, role FROM users").fetchall())
    assert roles["semak@kpt.test"] == "kpt" and roles["lihat@kpt.test"] == "executive" and roles["ipt@lama.test"] == "ipt"
    subs = c.execute("SELECT id, status, numerator, denominator, value, evidence_note FROM submissions ORDER BY id").fetchall()
    assert subs == [(1, "VERIFIED", 40.0, 1000.0, 4.0, "nota"), (2, "SUBMITTED", 12.0, None, 12.0, "")]
    assert c.execute("SELECT COUNT(*) FROM kpis").fetchone()[0] == 20
    assert c.execute("SELECT code FROM kpis WHERE id=17").fetchone()[0] == "T4/OS2/B"
    assert c.execute("SELECT value, kind FROM targets WHERE kpi_id=17 AND year=2026").fetchone() == (50.0, "milestone")
    assert c.execute("SELECT COUNT(*) FROM targets").fetchone()[0] == 100
    app = c.execute("SELECT status, inst_code, account_email, source FROM registration_applications").fetchall()
    assert app == [("PENDING_APPROVAL", "TUNGGU", "baru@tunggu.test", "LEGACY_V2B")]
    assert c.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 1
    assert c.execute("SELECT year, status FROM reporting_periods WHERE year=2026").fetchone() == (2026, "OPEN")
    c.close()
