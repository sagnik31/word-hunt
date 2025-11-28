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

import random
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional

SIM_PATH = "data/similarity.txt"
NOUNS_PATH = "data/common_nouns.txt"

logging.basicConfig(level=logging.INFO, format="%(message)s")


class WordGameEngine:
    """
    Engine for the hot-and-cold word guessing game.
    """

    def __init__(
        self,
        similarity_path: str = SIM_PATH,
        nouns_path: str = NOUNS_PATH,
        target_word: Optional[str] = None,
    ):
        self.similarity_path = Path(similarity_path)
        self.nouns_path = Path(nouns_path)

        if not self.similarity_path.exists():
            raise FileNotFoundError(f"similarity file not found: {self.similarity_path}")
        if not self.nouns_path.exists():
            raise FileNotFoundError(f"nouns file not found: {self.nouns_path}")

        self.vocab: List[str] = self._load_vocab()
        self.vocab_set = set(self.vocab)
        self.offsets: Dict[str, int] = self._build_line_index()

        vocab_in_similarity = set(self.offsets.keys())
        if not vocab_in_similarity:
            raise RuntimeError("No words found in similarity file.")

        # Target-related data
        self.target_word: str = ""
        self.target_similarity_list: List[Tuple[str, float]] = []
        self.target_pos_map: Dict[str, int] = {}
        self.target_total: int = 0

        self.set_target(target_word)

    def _load_vocab(self) -> List[str]:
        with open(self.nouns_path, "r", encoding="utf-8") as fh:
            text = fh.read()
        tokens = text.split()
        return [t.strip().lower() for t in tokens if t.strip()]

    def _build_line_index(self) -> Dict[str, int]:
        offsets: Dict[str, int] = {}
        with open(self.similarity_path, "r", encoding="utf-8") as fh:
            while True:
                pos = fh.tell()
                line = fh.readline()
                if not line:
                    break
                parts = line.split("\t", 1)
                if not parts:
                    continue
                word = parts[0].strip()
                if word:
                    offsets[word] = pos
        return offsets

    def _read_similarity_row_at(self, offset: int) -> List[Tuple[str, float]]:
        with open(self.similarity_path, "r", encoding="utf-8") as fh:
            fh.seek(offset)
            line = fh.readline()
        if not line:
            raise ValueError("Failed to read line at offset")

        parts = line.rstrip("\n").split("\t", 1)
        if len(parts) != 2:
            return []

        right = parts[1]
        if not right:
            return []

        pairs = right.split(",")
        result: List[Tuple[str, float]] = []
        for p in pairs:
            try:
                other, sc = p.rsplit(":", 1)
                result.append((other, float(sc)))
            except ValueError:
                continue
        return result

    @staticmethod
    def _describe_hotness(similarity_score: float) -> str:
        s = similarity_score
        if s >= 0.99:
            return "Correct"
        if s >= 0.90:
            return "Boiling"
        if s >= 0.75:
            return "Very hot"
        if s >= 0.60:
            return "Hot"
        if s >= 0.45:
            return "Warm"
        if s >= 0.30:
            return "Cool"
        if s >= 0.15:
            return "Cold"
        return "Freezing"

    def set_target(self, target_word: Optional[str] = None) -> str:
        available = list(self.offsets.keys())

        if target_word is not None:
            target_word = target_word.strip().lower()
            if target_word not in self.offsets:
                raise ValueError(f"Requested target not in similarity data: {target_word}")
            chosen = target_word
        else:
            chosen = random.choice(available)

        self.target_word = chosen

        offset = self.offsets[chosen]
        self.target_similarity_list = self._read_similarity_row_at(offset)
        self.target_total = len(self.target_similarity_list) + 1  # +1 for self

        self.target_pos_map = {w: idx for idx, (w, _) in enumerate(self.target_similarity_list)}

        return self.target_word

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

        Output dict:
          - word
          - rank
          - total
          - similarity
          - percentile
          - hotness
        """
        if not self.target_similarity_list:
            raise RuntimeError("Target similarity list is empty; engine not initialized properly.")

        n_others = len(self.target_similarity_list)
        k = min(max(top_n, 1), n_others)

        idx = random.randint(0, k - 1)
        word, sim = self.target_similarity_list[idx]
        rank = idx + 1

        total_others = max(1, self.target_total - 1)
        percentile = 100.0 * (1.0 - (rank - 1) / total_others)
        hotness = self._describe_hotness(sim)

        return {
            "word": word,
            "rank": rank,
            "total": self.target_total,
            "similarity": sim,
            "percentile": percentile,
            "hotness": hotness,
        }

    def make_guess(self, guess_word: str) -> Dict[str, Optional[object]]:
        guess_norm = (guess_word or "").strip().lower()

        base_response: Dict[str, Optional[object]] = {
            "guess": guess_norm,
            "valid": False,
            "error": None,
            "is_correct": None,
            "rank": None,
            "total": None,
            "similarity": None,
            "percentile": None,
            "hotness": None,
        }

        if not guess_norm:
            base_response["error"] = "Empty guess."
            return base_response

        if guess_norm not in self.vocab_set:
            base_response["error"] = "Word is not in the allowed vocabulary."
            return base_response

        if guess_norm not in self.offsets:
            base_response["error"] = "Word is missing from similarity data."
            return base_response

        base_response["valid"] = True

        if guess_norm == self.target_word:
            sim = 1.0
            rank = 1
            percentile = 100.0
            hotness = self._describe_hotness(sim)

            base_response.update(
                {
                    "is_correct": True,
                    "rank": rank,
                    "total": self.target_total,
                    "similarity": sim,
                    "percentile": percentile,
                    "hotness": hotness,
                }
            )
            return base_response

        if guess_norm in self.target_pos_map:
            idx = self.target_pos_map[guess_norm]
            rank = idx + 1
            sim = self.target_similarity_list[idx][1]
        else:
            idx = None
            sim = None
            for j, (w, sc) in enumerate(self.target_similarity_list):
                if w == guess_norm:
                    idx = j
                    sim = sc
                    break
            if idx is None or sim is None:
                base_response["error"] = "Internal error: guess not found in target similarity list."
                base_response["valid"] = False
                return base_response
            rank = idx + 1

        total_others = max(1, self.target_total - 1)
        percentile = 100.0 * (1.0 - (rank - 1) / total_others)
        hotness = self._describe_hotness(sim)

        base_response.update(
            {
                "is_correct": False,
                "rank": rank,
                "total": self.target_total,
                "similarity": sim,
                "percentile": percentile,
                "hotness": hotness,
            }
        )
        return base_response


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
            f"rank #{result['rank']}/{result['total']-1} | "
            f"sim={result['similarity']:.4f} "
            f"({result['percentile']:.1f} percentile) — {result['hotness']}"
        )


if __name__ == "__main__":
    _play_cli()