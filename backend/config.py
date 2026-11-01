from pathlib import Path

# Get the directory where this config file is located (backend/)
BACKEND_DIR = Path(__file__).resolve().parent
# Go up one level to get project root
BASE_DIR = BACKEND_DIR.parent
# Data directory is at project_root/data
DATA_DIR = BASE_DIR / "data"

SIMILARITY_PATH = DATA_DIR / "similarity.txt"
NOUNS_PATH = DATA_DIR / "common_nouns.txt"

CORS_ORIGINS = [
    "https://sagnik31.github.io",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
]
