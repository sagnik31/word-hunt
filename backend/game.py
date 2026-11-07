import random
import time
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

from backend.actions.guess import make_guess
from backend.actions.similar_word import get_similar_word
from backend.config import EMBEDDINGS_PATH, TARGET_WORDS_PATH, WORD_FORMS_PATH
from backend.utils.loaders import load_word_forms, load_word_list
from backend.utils.word_forms import plural_forms


class WordGameEngine:
    """
    Engine for the hot-and-cold word guessing game.

    Every guess word has a unit-length GloVe vector, so when a round starts the
    engine ranks all of them by cosine similarity to the answer (a few ms).
    """

    def __init__(
        self,
        embeddings_path: str = str(EMBEDDINGS_PATH),
        target_words_path: str = str(TARGET_WORDS_PATH),
        word_forms_path: str = str(WORD_FORMS_PATH),
        target_word: Optional[str] = None,
    ):
        data = np.load(embeddings_path)
        self.words = data["words"]  # numpy array, so a ranking can index it
        # float16 on disk; float32 for fast matrix products.
        self.vectors = data["vectors"].astype(np.float32)
        self.word_index: Dict[str, int] = {
            w: i for i, w in enumerate(self.words.tolist())
        }
        self.vocab_set: Set[str] = set(self.word_index)
        print(f"[WordGameEngine] Loaded {len(self.vocab_set)} guess words")

        self.targets: List[str] = [
            w for w in load_word_list(target_words_path) if w in self.word_index
        ]
        if not self.targets:
            raise RuntimeError("No target words have an embedding.")
        print(f"[WordGameEngine] Loaded {len(self.targets)} target words")

        # Plurals and verb forms accepted as their base word ("cats" -> "cat").
        self.word_forms: Dict[str, str] = load_word_forms(word_forms_path)
        print(f"[WordGameEngine] Loaded {len(self.word_forms)} extra word forms")

        # Target-related data
        self.target_word: str = ""
        self.target_plurals: Set[str] = set()
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

    def set_target(self, target_word: Optional[str] = None) -> str:
        if target_word is not None:
            chosen = target_word.strip().lower()
            if chosen not in self.targets:
                raise ValueError(f"Requested target is not a target word: {chosen}")
        else:
            # Don't repeat the word that was just played.
            candidates = [w for w in self.targets if w != self.target_word]
            chosen = random.choice(candidates or self.targets)

        # Rank every other guess word by similarity to the answer. The answer
        # itself is left out of the list (it's rank 1), so a hint can't reveal it.
        i = self.word_index[chosen]
        sims = self.vectors @ self.vectors[i]
        order = np.argsort(-sims, kind="stable")
        order = order[order != i]
        neighbours = list(zip(self.words[order].tolist(), sims[order].tolist()))

        self.target_word = chosen
        self.target_plurals = plural_forms(chosen) - {chosen}
        self.target_similarity_list = neighbours
        self.target_total = len(neighbours) + 1  # +1 for the answer
        self.target_pos_map = {w: idx for idx, (w, _) in enumerate(neighbours)}

        # Reset gameplay + scoring state
        self.best_rank_overall = None
        self.hint_count = 0
        self.similar_click_count = 0
        self.best_percentile = 0.0
        self.start_time = None  # starts on the first guess or help

        return self.target_word

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
            self.word_forms,
            self.target_plurals,
        )
        if result.get("valid"):
            self._update_best_rank(result.get("rank"))
            self._update_percentile(result.get("percentile"))
        return result
