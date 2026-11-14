import os
from datetime import date
from pathlib import Path
from typing import Optional

# Get the directory where this config file is located (backend/)
BACKEND_DIR = Path(__file__).resolve().parent
# Go up one level to get project root
BASE_DIR = BACKEND_DIR.parent
# Data directory is at project_root/data
DATA_DIR = BASE_DIR / "data"

# Built by backend/scripts/build_word_lists.py and extract_embeddings.py
EMBEDDINGS_PATH = DATA_DIR / "embeddings.npz"  # every guess word's vector
TARGET_WORDS_PATH = DATA_DIR / "target_words.txt"
WORD_FORMS_PATH = DATA_DIR / "word_forms.txt"
HINT_WORDS_PATH = DATA_DIR / "hint_words.txt"  # words ordinary enough to reveal

# Daily puzzle. Puzzle #1 is LAUNCH_DATE; a new puzzle starts at midnight UTC.
# Puzzle #1 went live on this day. Changing it shifts every puzzle's date.
LAUNCH_DATE = date(2026, 11, 8)

# Built by backend/scripts/build_schedule.py. One scrambled code per line, so
# the public repo doesn't give away future answers; decoding needs the key.
SCHEDULE_PATH = Path(os.environ.get("WORDHUNT_SCHEDULE_PATH", DATA_DIR / "daily_schedule.txt"))

# The schedule key: the WORDHUNT_SCHEDULE_KEY environment variable (Render),
# or a git-ignored schedule.key file at the repo root (your machine).
SCHEDULE_KEY_FILE = BASE_DIR / "schedule.key"

# Built by backend/scripts/generate_clues.py: three clues per answer, vague to
# strong, keyed by the same codes as the schedule so the file names no words.
CLUES_PATH = Path(os.environ.get("WORDHUNT_CLUES_PATH", DATA_DIR / "clues.json"))

# Results database for "you beat X% of today's players": a Postgres URL
# (Neon's pooled connection string, set on Render), or sqlite:///path for a
# local run. Unset, the game works as before and the results features are off.
# Never commit it.
DATABASE_URL_ENV = "DATABASE_URL"


def database_url() -> Optional[str]:
    return os.environ.get(DATABASE_URL_ENV, "").strip() or None


def schedule_key() -> Optional[str]:
    key = os.environ.get("WORDHUNT_SCHEDULE_KEY", "").strip()
    if key:
        return key
    if SCHEDULE_KEY_FILE.exists():
        return SCHEDULE_KEY_FILE.read_text(encoding="utf-8").strip() or None
    return None


CORS_ORIGINS = [
    "https://sagnik31.github.io",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
]
