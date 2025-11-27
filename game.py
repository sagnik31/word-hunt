#!/usr/bin/env python3
"""
game.py

Hardcoded:
  - similarity.txt
  - common_nouns.txt
"""
import random
import logging
from pathlib import Path
import sys

SIM_PATH = "similarity.txt"
NOUNS_PATH = "common_nouns.txt"

logging.basicConfig(level=logging.INFO, format="%(message)s")


def load_vocab():
    with open(NOUNS_PATH, "r", encoding="utf-8") as fh:
        text = fh.read()
    tokens = text.split()
    return [t.strip().lower() for t in tokens if t.strip()]


def build_index():
    offsets = {}
    with open(SIM_PATH, "r", encoding="utf-8") as fh:
        while True:
            pos = fh.tell()
            line = fh.readline()
            if not line:
                break
            word = line.split("\t", 1)[0]
            offsets[word] = pos
    return offsets


def read_row(word, offsets):
    pos = offsets[word]
    with open(SIM_PATH, "r", encoding="utf-8") as fh:
        fh.seek(pos)
        line = fh.readline()
    return line.split("\t", 1)[1].rstrip("\n")


def play():
    if not Path(SIM_PATH).exists() or not Path(NOUNS_PATH).exists():
        logging.error("Missing similarity.txt or common_nouns.txt")
        sys.exit(1)

    vocab = load_vocab()
    offsets = build_index()
    vocab = list(offsets.keys())  # ensure both files align

    target = random.choice(vocab)
    logging.info("🎯 Hot & Cold Word Game — Start!")
    logging.info("(Type 'quit' to exit)\n")

    # logging.info(f"The target word has been chosen: {target}!")
    target_row = read_row(target, offsets)
    pairs = target_row.split(",")
    mapping = {p.split(":")[0]: float(p.split(":")[1]) for p in pairs}
    

    total = len(mapping)

    while True:
        guess = input("Guess: ").strip().lower()

        if guess == "quit":
            print(f"The word was: {target}")
            break

        if guess not in mapping:
            print("Not in vocabulary / no similarity data.")
            continue

        score = mapping[guess]
        sorted_items = sorted(mapping.items(), key=lambda x: -x[1])
        top_50 = [w for w, _ in sorted_items[:50]]  # Extract top 50 words
        # print("Top 50 similar words:", ", ".join(top_50))  # Show the list

        rank = next(i+1 for i, (w, _) in enumerate(sorted_items) if w == guess)

        print(f"Rank={rank-1}")

        if guess == target:
            print("🎉 Correct! You win!")
            break


if __name__ == "__main__":
    play()