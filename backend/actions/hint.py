# hint.py — reveal an ordinary word ranked just better than the player's best

import os
import random
from typing import TYPE_CHECKING, Dict, Optional, Tuple

import numpy as np

from backend.utils.scoring import compute_percentile, describe_hotness

if TYPE_CHECKING:
    from backend.game import Ranking

# The ranks each hint reveals from: Hint 1 a word ranked 6-10, Hint 2 one
# ranked 2-5 (the answer is rank 1, so it's never revealed).
HINT_RANKS: Tuple[Tuple[int, int], ...] = ((6, 10), (2, 5))

# A hint avoids words built on the answer's stem ("stimulate" for
# "stimulus", "spoonful" for "teaspoonful"), which all but give it away:
# a shared start or end of at least this many letters, covering all but 2
# letters of the shorter word when the two only share a start.
STEM_MIN_LETTERS = 4
STEM_SLACK = 2


def shares_stem(answer: str, word: str) -> bool:
    """True when `word` is the answer with a different ending, or one part
    of a compound answer (or the answer is part of it)."""
    short, long = sorted((answer, word), key=len)
    if len(short) >= STEM_MIN_LETTERS and (long.startswith(short) or long.endswith(short)):
        return True
    common = len(os.path.commonprefix([answer, word]))
    return common >= STEM_MIN_LETTERS and common >= len(short) - STEM_SLACK


def hint_ranks(hints_used: int, best_rank: Optional[int]) -> Optional[Tuple[int, int]]:
    """Ranks the next hint picks from, or None when there's nothing to give.

    The revealed word always beats the player's best, so a best inside the
    range shrinks it to stay below; with a best of #2 only the answer is left.
    """
    if hints_used >= len(HINT_RANKS):
        return None
    low, high = HINT_RANKS[hints_used]
    if best_rank is not None:
        high = min(high, best_rank - 1)
        low = min(low, high)
    if high < 2:
        return None
    return low, high


def get_hint(
    ranking: "Ranking",
    ranks: Tuple[int, int],
    allowed: np.ndarray,
) -> Optional[Dict[str, object]]:
    """A word ranked within `ranks`, preferring `allowed` (ordinary) words
    that don't share the answer's stem.

    A word on the answer's stem is used only when nothing else is in the
    range, and a rare word only when no ordinary one is. A form of the
    answer (a plural) is never revealed, since typing it wins; when nothing
    else is in the range, a closer word is used, or None if there's none.
    """
    low, high = ranks
    high = min(high, len(ranking.order) + 1)

    def word_at(p):  # rank r is position r - 2
        return str(ranking.words[ranking.order[p]])

    def fit(low, high):
        return [p for p in range(low - 2, high - 1) if word_at(p) not in ranking.answer_forms]

    positions = fit(low, high) or fit(2, low - 1)
    if not positions:
        return None
    fair = [p for p in positions if not shares_stem(ranking.answer, word_at(p))] or positions
    ordinary = [p for p in fair if allowed[ranking.order[p]]]
    word, sim, rank = ranking.neighbour(random.choice(ordinary or fair))
    return {
        "word": word,
        "rank": rank,
        "total": ranking.total,
        "similarity": sim,
        "percentile": compute_percentile(rank, ranking.total),
        "hotness": describe_hotness(rank),
    }
