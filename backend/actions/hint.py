# hint.py — reveal an ordinary word ranked just better than the player's best

import random
from typing import TYPE_CHECKING, Dict, Optional, Tuple

import numpy as np

from backend.utils.scoring import compute_percentile, describe_hotness

if TYPE_CHECKING:
    from backend.game import Ranking

# The ranks each hint reveals from: Hint 1 a word ranked 6-10, Hint 2 one
# ranked 2-5 (the answer is rank 1, so it's never revealed).
HINT_RANKS: Tuple[Tuple[int, int], ...] = ((6, 10), (2, 5))


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
) -> Dict[str, object]:
    """A word ranked within `ranks`, preferring `allowed` (ordinary) words.

    If no ordinary word falls in the range (rare), any word in it will do.
    """
    low, high = ranks
    high = min(high, len(ranking.order) + 1)
    positions = range(low - 2, high - 1)  # rank r is position r - 2
    ordinary = [p for p in positions if allowed[ranking.order[p]]]
    word, sim, rank = ranking.neighbour(random.choice(ordinary or list(positions)))
    return {
        "word": word,
        "rank": rank,
        "total": ranking.total,
        "similarity": sim,
        "percentile": compute_percentile(rank, ranking.total),
        "hotness": describe_hotness(rank),
    }
