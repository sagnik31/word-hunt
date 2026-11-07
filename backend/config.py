from pathlib import Path

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

CORS_ORIGINS = [
    "https://sagnik31.github.io",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
]
