#!/usr/bin/env python3
"""
Write data/embeddings.npz: a GloVe vector for every guess word.

Run from the repository root, after build_word_lists.py:
    python backend/scripts/extract_embeddings.py

Inputs:
  - data/guess_words.txt    one word per line
  - data/glove.6B.300d.txt  GloVe 6B 300d vectors (1 GB, not committed)

Output arrays:
  - words    the guess words, in file order
  - vectors  one unit-length float16 row per word, so a dot product is the
             cosine similarity (float16 halves the file and memory size)
"""

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
GLOVE_PATH = ROOT / "data" / "glove.6B.300d.txt"
WORDS_PATH = ROOT / "data" / "guess_words.txt"
OUT_PATH = ROOT / "data" / "embeddings.npz"
DIMENSIONS = 300


def extract():
    for path in (GLOVE_PATH, WORDS_PATH):
        if not path.exists():
            sys.exit(f"Missing input: {path}")

    words = WORDS_PATH.read_text(encoding="utf-8").split()
    wanted = set(words)
    print(f"Looking up {len(words)} words in {GLOVE_PATH.name} ...")

    found = {}
    with open(GLOVE_PATH, encoding="utf-8") as fh:
        for line in fh:
            token, _, rest = line.partition(" ")
            if token in wanted and token not in found:
                vec = np.array(rest.split(), dtype=np.float32)
                if vec.shape == (DIMENSIONS,):
                    found[token] = vec

    missing = [w for w in words if w not in found]
    if missing:
        sys.exit(
            f"{len(missing)} guess words have no GloVe vector, e.g. {missing[:10]}. "
            "Rerun build_word_lists.py, which only keeps words GloVe knows."
        )

    vectors = np.vstack([found[w] for w in words])
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)

    np.savez_compressed(
        OUT_PATH, words=np.array(words), vectors=vectors.astype(np.float16)
    )
    size_mb = OUT_PATH.stat().st_size / 1e6
    print(f"Saved {len(words)} vectors to {OUT_PATH.name} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    extract()
