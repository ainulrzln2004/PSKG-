"""Runtime configuration read from environment variables (or a local .env file).

No secrets are hard-coded. Every value has a safe development default so that the
application can be started on Windows/macOS with `python -m uvicorn app.main:app`.
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader (KEY=VALUE lines). Existing environment variables win."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv(BASE_DIR / ".env")


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


class Settings:
    def __init__(self) -> None:
        self.env = os.getenv("APP_ENV", "development").lower()
        self.database_url = os.getenv("DATABASE_URL", f"sqlite:///{(BASE_DIR / 'pskg_dev.db').as_posix()}")
        self.public_url = os.getenv("PUBLIC_URL", "http://localhost:8000").rstrip("/")
        self.session_hours = _int("SESSION_HOURS", 8)
        self.cookie_secure = _bool("COOKIE_SECURE", self.env == "production")
        self.auto_migrate = _bool("AUTO_MIGRATE", True)
        self.storage_dir = Path(os.getenv("STORAGE_DIR", str(BASE_DIR / "storage")))
        self.max_upload_mb = _int("MAX_UPLOAD_MB", 10)
        self.invitation_hours = _int("INVITATION_HOURS", 72)
        self.reset_hours = _int("PASSWORD_RESET_HOURS", 2)
        # Login rate limiting
        self.login_max_failures = _int("LOGIN_MAX_FAILURES", 5)
        self.login_window_minutes = _int("LOGIN_WINDOW_MINUTES", 15)
        self.ip_max_failures = _int("LOGIN_IP_MAX_FAILURES", 30)
        self.public_form_limit = _int("PUBLIC_FORM_LIMIT_PER_HOUR", 20)
        # SMTP (optional). If SMTP_HOST is empty, emails are stored as development previews.
        self.smtp_host = os.getenv("SMTP_HOST", "")
        self.smtp_port = _int("SMTP_PORT", 587)
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.smtp_from = os.getenv("SMTP_FROM", "no-reply@pskg.local")
        self.smtp_starttls = _bool("SMTP_STARTTLS", True)

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def smtp_enabled(self) -> bool:
        return bool(self.smtp_host)

    @property
    def evidence_dir(self) -> Path:
        return self.storage_dir / "evidence"


settings = Settings()

YEARS = [2026, 2027, 2028, 2029, 2030]

INSTITUTION_CATEGORIES = {
    "UA": "Universiti Awam",
    "IPTS": "IPTS",
    "POLITEKNIK": "Politeknik",
    "KK": "Kolej Komuniti",
}

# Official population of institutions per category as stated on slide 38 of
# PSKG_final_KPI.pptx. Used only as a *reference* for national coverage figures.
OFFICIAL_INSTITUTION_POPULATION = {"UA": 20, "IPTS": 357, "POLITEKNIK": 36, "KK": 106}

STATES = [
    "Johor", "Kedah", "Kelantan", "Melaka", "Negeri Sembilan", "Pahang", "Perak", "Perlis",
    "Pulau Pinang", "Sabah", "Sarawak", "Selangor", "Terengganu",
    "W.P. Kuala Lumpur", "W.P. Labuan", "W.P. Putrajaya",
]

DEFAULT_PILOT_NOTICE = (
    "PERSEKITARAN PILOT: Sasaran KPI merujuk jadual PSKG akhir; formula dan takrif "
    "pembilang/penyebut yang belum diperakukan masih dalam semakan. Dashboard hanya "
    "memaparkan data diluluskan. Jangan masukkan data peribadi graduan atau data rasmi "
    "tanpa kebenaran KPT."
)
