from collections import OrderedDict
from typing import Dict, Iterable, Optional, Set

import numpy as np

from backend.actions.guess import make_guess
from backend.actions.similar_word import get_similar_word
from backend.config import EMBEDDINGS_PATH, WORD_FORMS_PATH
from backend.utils.loaders import load_word_forms
from backend.utils.word_forms import plural_forms


class Ranking:
    """Every guess word ranked by similarity to one answer."""

    def __init__(self, answer: str, words: np.ndarray, sims: np.ndarray, answer_index: int):
        self.answer = answer
        self.plurals: Set[str] = plural_forms(answer) - {answer}
        # Word indices, closest first, without the answer (it's rank 1, and
        # leaving it out means a hint can never reveal it).
        order = np.argsort(-sims, kind="stable")
        self.order = order[order != answer_index].astype(np.int32)
        self.sims = sims
        self.words = words
        # rank_of[i] is word i's rank; the closest neighbour is rank 2.
        self.rank_of = np.empty(len(words), dtype=np.int32)
        self.rank_of[self.order] = np.arange(2, len(self.order) + 2, dtype=np.int32)
        self.rank_of[answer_index] = 1
        self.total = len(words)

    def neighbour(self, position: int):
        """(word, similarity, rank) for 0-based position among the others."""
        i = int(self.order[position])
        return str(self.words[i]), float(self.sims[i]), position + 2


class WordGameEngine:
    """
    Stateless engine for the daily hot-and-cold puzzle.

    It only knows the vocabulary and how to rank it against an answer; the
    player's progress (guesses, help used, timer) lives in their browser and
    comes in with each request. Rankings are cached for the last few answers.
    """

    CACHE_SIZE = 16  # ~0.4 MB per answer

    def __init__(
        self,
        embeddings_path: str = str(EMBEDDINGS_PATH),
        word_forms_path: str = str(WORD_FORMS_PATH),
    ):
        data = np.load(embeddings_path)
        self.words = data["words"]  # numpy array, so a ranking can index it
        # float16 on disk; float32 for fast matrix products.
        self.vectors = data["vectors"].astype(np.float32)
        self.word_index: Dict[str, int] = {w: i for i, w in enumerate(self.words.tolist())}
        self.vocab_set: Set[str] = set(self.word_index)
        print(f"[WordGameEngine] Loaded {len(self.vocab_set)} guess words")

        # Plurals and verb forms accepted as their base word ("cats" -> "cat").
        self.word_forms: Dict[str, str] = load_word_forms(word_forms_path)
        print(f"[WordGameEngine] Loaded {len(self.word_forms)} extra word forms")

        self._rankings: "OrderedDict[str, Ranking]" = OrderedDict()

    @property
    def vocabulary(self) -> Iterable[str]:
        return self.vocab_set

    def ranking(self, answer: str) -> Ranking:
        cached = self._rankings.get(answer)
        if cached is not None:
            self._rankings.move_to_end(answer)
            return cached
        i = self.word_index[answer]
        ranking = Ranking(answer, self.words, self.vectors @ self.vectors[i], i)
        self._rankings[answer] = ranking
        if len(self._rankings) > self.CACHE_SIZE:
            self._rankings.popitem(last=False)
        return ranking

    @staticmethod
    def hint_strength(times_used: int) -> str:
        """The first 3 uses of a help feature are 'soft', later ones 'strong'."""
        return "soft" if times_used < 3 else "strong"

    def guess(self, answer: str, word: str) -> Dict[str, Optional[object]]:
        return make_guess(word, self.ranking(answer), self.word_index, self.word_forms)

    def suggest(self, answer: str, best_rank: Optional[int], times_used: int) -> Dict[str, object]:
        """A word ranked better than best_rank (Hint and Similar Word)."""
        return get_similar_word(self.ranking(answer), best_rank, self.hint_strength(times_used))
