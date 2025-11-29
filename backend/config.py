import os
from pathlib import Path

# Get the directory where this config file is located (backend/)
BACKEND_DIR = Path(__file__).resolve().parent
# Go up one level to get project root
BASE_DIR = BACKEND_DIR.parent
# Data directory is at project_root/data
DATA_DIR = BASE_DIR / "data"

SIMILARITY_PATH = DATA_DIR / "similarity.txt"
NOUNS_PATH = DATA_DIR / "common_nouns.txt"

# Debug logging
print(f"[config] BACKEND_DIR: {BACKEND_DIR}")
print(f"[config] BASE_DIR: {BASE_DIR}")
print(f"[config] DATA_DIR: {DATA_DIR}")
print(f"[config] SIMILARITY_PATH: {SIMILARITY_PATH}")
print(f"[config] NOUNS_PATH: {NOUNS_PATH}")
print(f"[config] Similarity file exists: {SIMILARITY_PATH.exists()}")
print(f"[config] Nouns file exists: {NOUNS_PATH.exists()}")

CORS_ORIGINS = [
    "https://sagnik31.github.io",
    "https://sagnik31.github.io/word-hunt",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
]
