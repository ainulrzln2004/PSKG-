"""Apply database migrations (safe to run repeatedly).

Run:  python -m scripts.migrate
"""
from app.config import settings
from app.migrate import upgrade_to_head

if __name__ == "__main__":
    upgrade_to_head()
    print(f"Pangkalan data dikemas kini ke versi terkini: {settings.database_url.split('@')[-1]}")
