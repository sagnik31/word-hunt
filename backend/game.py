import logging
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from backend.actions.guess import make_guess
from backend.actions.similar_word import get_similar_word
from backend.actions.hint import get_hint  # if you still use this elsewhere
from backend.config import NOUNS_PATH, SIMILARITY_PATH
from backend.utils.loaders import build_line_index, load_vocab, read_similarity_row

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

        # Game state: best rank across guesses + hints, and number of hints
        self.best_rank_overall: Optional[int] = None
        self.hint_count: int = 0

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

                # Reset game state when changing target
                self.best_rank_overall = None
                self.hint_count = 0

                return self.target_word

        raise RuntimeError("Could not find a target with a non-empty similarity list.")

    def get_target(self) -> str:
        return self.target_word

    def get_answer(self) -> str:
        """
        Return the current target word (for quit endpoint / debugging).
        """
        return self.target_word

    # --- New helper state methods ---------------------------------------

    def _update_best_rank(self, rank: int) -> None:
        if rank is None:
            return
        if self.best_rank_overall is None:
            self.best_rank_overall = rank
        else:
            self.best_rank_overall = min(self.best_rank_overall, rank)

    def _determine_hint_strength(self) -> str:
        """
        First 3 hints are 'soft', subsequent ones are 'strong'.
        """
        if self.hint_count < 3:
            return "soft"
        return "strong"

    # --- Hint / similar word endpoints ----------------------------------

    def get_similar_word(self) -> Dict[str, object]:
        """
        Backend decides whether the hint is soft or strong based on how many
        hints have already been given.
        """
        strength = self._determine_hint_strength()
        hint = get_similar_word(
            self.target_similarity_list,
            self.target_total,
            self.best_rank_overall,
            strength,
        )

        # Update state
        self.hint_count += 1
        self._update_best_rank(hint.get("rank"))

        return hint

    def get_hint(self) -> Dict[str, object]:
       """
        Backend decides whether the hint is soft or strong based on how many
        hints have already been given.
        """
       strength = self._determine_hint_strength()
       hint = get_hint(
            self.target_similarity_list,
            self.target_total,
            self.best_rank_overall,
            strength,
        )
       self.hint_count += 1
       self._update_best_rank(hint.get("rank"))
       return hint

    # --- Guess handling -------------------------------------------------

    def make_guess(self, guess_word: str) -> Dict[str, Optional[object]]:
        result = make_guess(
            guess_word,
            self.target_word,
            self.target_similarity_list,
            self.target_pos_map,
            self.target_total,
            self.vocab_set,
            self.offsets,
        )

        # Update best_rank_overall based on guess rank
        if result.get("valid") and result.get("rank") is not None:
            self._update_best_rank(result["rank"])

        return result
