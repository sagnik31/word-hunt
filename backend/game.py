from collections import OrderedDict
from typing import Dict, Iterable, Optional, Set

import numpy as np

from backend.actions.guess import make_guess
from backend.actions.hint import get_hint, hint_ranks
from backend.config import EMBEDDINGS_PATH, HINT_WORDS_PATH, WORD_FORMS_PATH
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
        hint_words_path: str = str(HINT_WORDS_PATH),
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

        # Which words a Hint may reveal; every word if the list is missing.
        try:
            with open(hint_words_path, encoding="utf-8") as fh:
                hint_words = {line.strip() for line in fh if line.strip()}
            self.hint_ok = np.array([w in hint_words for w in self.words.tolist()])
        except FileNotFoundError:
            print(f"[WordGameEngine] {hint_words_path} missing; hints may reveal any word")
            self.hint_ok = np.ones(len(self.words), dtype=bool)
        print(f"[WordGameEngine] {int(self.hint_ok.sum())} words can be hints")

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

    def guess(self, answer: str, word: str) -> Dict[str, Optional[object]]:
        return make_guess(word, self.ranking(answer), self.word_index, self.word_forms)

    def hint(self, answer: str, best_rank: Optional[int], hints_used: int) -> Optional[Dict[str, object]]:
        """The next hint's word, or None when no hint is left to give."""
        ranks = hint_ranks(hints_used, best_rank)
        if ranks is None:
            return None
        return get_hint(self.ranking(answer), ranks, self.hint_ok)
