import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

SIMILARITY_PATH = DATA_DIR / "similarity.txt"
NOUNS_PATH = DATA_DIR / "common_nouns.txt"

CORS_ORIGINS = [
    "https://sagnik31.github.io",
    "https://sagnik31.github.io/word-hunt",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
]
