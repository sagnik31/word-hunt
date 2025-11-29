#!/usr/bin/env python3
"""
game.py

Core word game engine.

Hardcoded files:
  - similarity.txt
  - common_nouns.txt

Main class:
  - WordGameEngine

Key methods:
  - make_guess(guess_word: str) -> dict
  - set_target(target_word: Optional[str] = None) -> str
  - get_target() -> str
  - get_hint(top_n: int = 10) -> dict
  - get_answer() -> str
"""

import logging
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from backend.actions.guess import make_guess
from backend.actions.hint import get_hint
from backend.config import NOUNS_PATH, SIMILARITY_PATH
from backend.utils.loaders import (build_line_index, load_vocab,
                                   read_similarity_row)

logging.basicConfig(level=logging.INFO, format="%(message)s")


class WordGameEngine:
    """
    Engine for the hot-and-cold word guessing game.
    """

    def __init__(
        self,
        similarity_path: str = str(SIMILARITY_PATH),
        nouns_path: str = str(NOUNS_PATH),
        target_word: Optional[str] = None,
    ):
        self.similarity_path = Path(similarity_path)
        self.nouns_path = Path(nouns_path)

        print(f"[WordGameEngine]   similarity_path: {self.similarity_path}")
        print(f"[WordGameEngine]   nouns_path: {self.nouns_path}")
        print(
            f"[WordGameEngine]   Files exist: similarity={self.similarity_path.exists()}, nouns={self.nouns_path.exists()}"
        )

        if not self.similarity_path.exists():
            raise FileNotFoundError(
                f"similarity file not found: {self.similarity_path}"
            )
        if not self.nouns_path.exists():
            raise FileNotFoundError(f"nouns file not found: {self.nouns_path}")

        self.vocab: List[str] = load_vocab(str(self.nouns_path))
        self.vocab_set = set(self.vocab)
        print(f"[WordGameEngine] Loaded {len(self.vocab)} vocabulary words")
        if len(self.vocab) > 0:
            print(f"[WordGameEngine] First few words: {self.vocab[:10]}")

        self.offsets: Dict[str, int] = build_line_index(str(self.similarity_path))
        print(
            f"[WordGameEngine] Built index for {len(self.offsets)} words in similarity file"
        )

        vocab_in_similarity = set(self.offsets.keys())
        if not vocab_in_similarity:
            raise RuntimeError("No words found in similarity file.")

        # Target-related data
        self.target_word: str = ""
        self.target_similarity_list: List[Tuple[str, float]] = []
        self.target_pos_map: Dict[str, int] = {}
        self.target_total: int = 0

        self.set_target(target_word)
        print(
            f"[WordGameEngine] Initialized successfully with target: {self.target_word}"
        )

    def set_target(self, target_word: Optional[str] = None) -> str:
        available = list(self.offsets.keys())

        # If a specific target is requested, use it and validate once
        if target_word is not None:
            target_word = target_word.strip().lower()
            if target_word not in self.offsets:
                raise ValueError(
                    f"Requested target not in similarity data: {target_word}"
                )
            candidates = [target_word]
        else:
            candidates = available

        for _ in range(len(candidates) * 3):  # some upper bound on attempts
            chosen = random.choice(candidates)
            offset = self.offsets[chosen]
            sims = read_similarity_row(str(self.similarity_path), offset)

            if sims:  # only accept targets with non-empty similarity list
                self.target_word = chosen
                self.target_similarity_list = sims
                self.target_total = len(sims) + 1  # +1 for self
                self.target_pos_map = {w: idx for idx, (w, _) in enumerate(sims)}
                return self.target_word

        raise RuntimeError("Could not find a target with a non-empty similarity list.")

    def get_target(self) -> str:
        return self.target_word

    def get_answer(self) -> str:
        """
        Return the current target word (for quit endpoint / debugging).
        """
        return self.target_word

    def get_hint(self, top_n: int = 10) -> Dict[str, object]:
        """
        Return a 'hot' word: randomly chosen from the top-N most similar words
        to the target (excluding the target itself).
        """
        return get_hint(self.target_similarity_list, self.target_total, top_n)

    def make_guess(self, guess_word: str) -> Dict[str, Optional[object]]:
        return make_guess(
            guess_word,
            self.target_word,
            self.target_similarity_list,
            self.target_pos_map,
            self.target_total,
            self.vocab_set,
            self.offsets,
        )


# CLI mode for local testing (unchanged)
def _play_cli():
    try:
        engine = WordGameEngine()
    except Exception as e:
        logging.error(f"Failed to start game engine: {e}")
        return

    logging.info("🎯 Hot & Cold Word Game — CLI mode")
    logging.info("Type 'quit' to exit. Type 'target' to reveal the word (debug).")
    logging.info("")

    while True:
        try:
            guess = input("Guess> ")
        except (KeyboardInterrupt, EOFError):
            print()
            logging.info("Goodbye.")
            return

        guess_strip = guess.strip().lower()
        if guess_strip == "quit":
            logging.info(f"Target was: {engine.get_target()}")
            return
        if guess_strip == "target":
            logging.info(f"[DEBUG] Current target: {engine.get_target()}")
            continue

        result = engine.make_guess(guess)
        if not result["valid"]:
            logging.info(f"Invalid guess: {result['error']}")
            continue

        if result["is_correct"]:
            logging.info("🎉 Correct! You found the target word.")
            logging.info(
                f"Word: {result['guess']} | rank={result['rank']} "
                f"| similarity={result['similarity']:.4f}"
            )
            return

        logging.info(
            f"Guess: '{result['guess']}' | "
            f"rank #{result['rank']}/{result['total'] - 1} | "
            f"sim={result['similarity']:.4f} "
            f"({result['percentile']:.1f} percentile) — {result['hotness']}"
        )


if __name__ == "__main__":
    _play_cli()
