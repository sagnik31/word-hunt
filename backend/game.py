import random
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from backend.actions.guess import make_guess
from backend.actions.similar_word import get_similar_word
from backend.config import NOUNS_PATH, SIMILARITY_PATH
from backend.utils.loaders import build_line_index, load_vocab, read_similarity_row


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

        # Gameplay state
        self.best_rank_overall: Optional[int] = None

        # Scoring-related state
        self.start_time: Optional[float] = None
        self.hint_count: int = 0
        self.similar_click_count: int = 0
        self.best_percentile: float = 0.0

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
            # Don't repeat the word that was just played.
            candidates = [w for w in available if w != self.target_word] or available

        for _ in range(len(candidates) * 3):  # some upper bound on attempts
            chosen = random.choice(candidates)
            offset = self.offsets[chosen]
            sims = read_similarity_row(str(self.similarity_path), offset)

            # The ranking must not contain the target itself or repeated
            # words, or a hint could reveal the answer.
            seen = {chosen}
            neighbours: List[Tuple[str, float]] = []
            for w, s in sims:
                if w not in seen:
                    seen.add(w)
                    neighbours.append((w, s))

            if neighbours:  # only accept targets with non-empty similarity list
                self.target_word = chosen
                self.target_similarity_list = neighbours
                self.target_total = len(neighbours) + 1  # +1 for self
                self.target_pos_map = {
                    w: idx for idx, (w, _) in enumerate(neighbours)
                }

                # Reset gameplay + scoring state
                self.best_rank_overall = None
                self.hint_count = 0
                self.similar_click_count = 0
                self.best_percentile = 0.0
                self.start_time = None  # starts on the first guess or help

                return self.target_word

        raise RuntimeError("Could not find a target with a non-empty similarity list.")

    def get_target(self) -> str:
        return self.target_word

    # --- State update helpers -------------------------------------------

    def _update_best_rank(self, rank: int) -> None:
        if rank is None:
            return
        if self.best_rank_overall is None:
            self.best_rank_overall = rank
        else:
            self.best_rank_overall = min(self.best_rank_overall, rank)

    def _update_percentile(self, percentile: Optional[float]) -> None:
        if percentile is None:
            return
        if percentile > self.best_percentile:
            self.best_percentile = percentile

    def _start_clock(self) -> None:
        if self.start_time is None:
            self.start_time = time.time()

    @staticmethod
    def _determine_hint_strength(times_used: int) -> str:
        """
        The first 3 uses of a help feature are 'soft', later ones 'strong'.
        """
        if times_used < 3:
            return "soft"
        return "strong"

    # --- Similar Word / Hint --------------------------------------------
    # Both reveal a word ranked better than the player's best so far;
    # each tracks its own use count, which sets its strength.

    def _suggest_word(self, times_used: int) -> Dict[str, object]:
        self._start_clock()
        strength = self._determine_hint_strength(times_used)
        hint = get_similar_word(
            self.target_similarity_list,
            self.target_total,
            self.best_rank_overall,
            strength,
        )
        self._update_best_rank(hint.get("rank"))
        self._update_percentile(hint.get("percentile"))
        return hint

    def get_similar_word(self) -> Dict[str, object]:
        hint = self._suggest_word(self.similar_click_count)
        self.similar_click_count += 1
        return hint

    def get_hint(self) -> Dict[str, object]:
        hint = self._suggest_word(self.hint_count)
        self.hint_count += 1
        return hint

    # --- Guess handling -------------------------------------------------

    def make_guess(self, guess_word: str) -> Dict[str, Optional[object]]:
        self._start_clock()
        result = make_guess(
            guess_word,
            self.target_word,
            self.target_similarity_list,
            self.target_pos_map,
            self.target_total,
            self.vocab_set,
            self.offsets,
        )
        if result.get("valid"):
            self._update_best_rank(result.get("rank"))
            self._update_percentile(result.get("percentile"))
        return result
