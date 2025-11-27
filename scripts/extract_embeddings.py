#!/usr/bin/env python3
"""
extract_embeddings.py

Hardcoded:
  - GloVe path: glove.6B.300d.txt
  - nouns path: common_nouns.txt

Outputs:
  - embeddings.npz
  - missing.txt
"""

import sys
import numpy as np
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

GLOVE_PATH = "data/glove.6B.300d.txt"
NOUNS_PATH = "data/common_nouns.txt"
OUT_PATH = "data/embeddings.npz"
MISSING_PATH = "data/missing.txt"


def read_nouns(path: str):
    """
    Read nouns from a file where words can be separated by spaces and/or newlines.
    Example content:
        aardvark abyssinian accelerator accordion account ...
    """
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    tokens = text.split()  # splits on all whitespace
    nouns = [t.strip().lower() for t in tokens if t.strip()]
    return nouns


def extract():
    # File existence checks
    if not Path(GLOVE_PATH).exists():
        logging.error(f"GloVe file not found: {GLOVE_PATH}")
        sys.exit(1)

    if not Path(NOUNS_PATH).exists():
        logging.error(f"Nouns file not found: {NOUNS_PATH}")
        sys.exit(1)

    nouns = read_nouns(NOUNS_PATH)
    if not nouns:
        logging.error(f"No nouns could be read from {NOUNS_PATH}. Check the file content.")
        sys.exit(1)

    nouns_set = set(nouns)
    logging.info(f"Looking for {len(nouns_set)} nouns in GloVe...")

    found_vectors = {}
    found_count = 0

    # Read GloVe and grab only relevant words
    with open(GLOVE_PATH, "r", encoding="utf-8") as gh:
        for line in gh:
            parts = line.rstrip().split(" ")
            if len(parts) < 301:
                continue  # malformed line

            token = parts[0].lower()
            if token in nouns_set:
                try:
                    vec = np.asarray(parts[1:], dtype=np.float32)
                except ValueError:
                    # if any float conversion fails, skip this line
                    continue

                if vec.shape[0] == 300:
                    if token not in found_vectors:  # avoid overwriting
                        found_vectors[token] = vec
                        found_count += 1
                        if found_count % 100 == 0:
                            logging.info(f"Found {found_count}/{len(nouns_set)}")

    # Identify missing nouns
    missing = [w for w in nouns if w not in found_vectors]
    if missing:
        logging.warning(f"{len(missing)} nouns missing — saving to {MISSING_PATH}")
        with open(MISSING_PATH, "w", encoding="utf-8") as mfh:
            for w in missing:
                mfh.write(w + "\n")
    else:
        logging.info("All nouns were found in GloVe.")

    # Keep only the nouns that we actually found embeddings for, in original order
    valid_words = [w for w in nouns if w in found_vectors]

    if not valid_words:
        logging.error(
            "No embeddings were found for any of the nouns. "
            "Check that your GloVe file and nouns file are compatible (e.g., both lowercase)."
        )
        sys.exit(1)

    embedding_matrix = np.vstack([found_vectors[w] for w in valid_words])

    logging.info(f"Saving {len(valid_words)} embeddings to {OUT_PATH}")
    np.savez_compressed(OUT_PATH, words=np.array(valid_words, dtype=object), embeddings=embedding_matrix)

    logging.info("Done!")


if __name__ == "__main__":
    extract()