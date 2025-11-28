#!/usr/bin/env python3
"""
build_similarity.py

Hardcoded:
  - embeddings.npz -> input
  - similarity.txt -> output

Output format (tab-separated):
  word<TAB>other1:score,other2:score,...

The "other" words are sorted descending by cosine similarity
and do NOT include the word itself.
"""

import sys
import numpy as np
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

EMB_PATH = "data/embeddings.npz"
OUT_PATH = "data/similarity.txt"


def normalize_rows(x: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return x / norms


def main():
    if not Path(EMB_PATH).exists():
        logging.error(f"Embeddings file not found: {EMB_PATH}")
        sys.exit(1)

    data = np.load(EMB_PATH, allow_pickle=True)
    words = data["words"].tolist()
    emb = data["embeddings"].astype(np.float32)

    logging.info(f"Computing similarities for {len(words)} words...")

    emb = normalize_rows(emb)
    sim = np.matmul(emb, emb.T)
    np.clip(sim, -1.0, 1.0, out=sim)

    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        for i, w in enumerate(words):
            row = sim[i].copy()
            row[i] = -2.0  # exclude itself
            idx = np.argsort(-row)
            pairs = [f"{words[j]}:{sim[i][j]:.6f}" for j in idx]
            fh.write(f"{w}\t{','.join(pairs)}\n")

    logging.info(f"Saved similarity data to {OUT_PATH}")


if __name__ == "__main__":
    main()
