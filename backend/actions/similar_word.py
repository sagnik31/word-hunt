# similar_word.py — pick a word ranked better than the player's best

import random
from typing import TYPE_CHECKING, Dict, Literal, Optional

from backend.utils.scoring import compute_percentile, describe_hotness

if TYPE_CHECKING:
    from backend.game import Ranking

HintStrength = Literal["soft", "strong"]


def _choose_hint_index(
    n_others: int,
    best_position: Optional[int],
    hint_strength: HintStrength
) -> int:
    """
    Select an index whose 1-based neighbour position is better (lower) than
    best_position if possible.
    Soft = modest improvement
    Strong = aggressive improvement
    """
    if best_position is None or best_position > 100:
        # Player still far — big window
        if hint_strength == "strong":
            low_rank, high_rank = 1, min(50, n_others)
        else:  # soft
            low_rank, high_rank = 50, min(100, n_others)
            if low_rank > n_others:
                low_rank, high_rank = 1, min(20, n_others)
    else:
        # User already mid-close — give strictly better hint
        best = min(best_position, n_others)
        if best <= 1:
            low_rank, high_rank = 1, min(5, n_others)
        else:
            if hint_strength == "strong":
                low_rank, high_rank = 1, best - 1
            else:
                improvement_window = max(5, best // 2)
                low_rank = max(1, best - improvement_window)
                high_rank = best - 1

    low_rank = max(1, min(low_rank, n_others))
    high_rank = max(1, min(high_rank, n_others))

    if low_rank > high_rank:
        low_rank, high_rank = 1, min(20, n_others)

    return random.randint(low_rank - 1, high_rank - 1)


def get_similar_word(
    ranking: "Ranking",
    best_rank_overall: Optional[int],
    hint_strength: HintStrength = "strong",
) -> Dict[str, object]:
    """
    Returns: a dict with:
      word, rank, total, similarity, percentile, hotness
    Ensures hint rank improves the user's best rank when possible.
    """
    n_others = len(ranking.order)
    if not n_others:
        raise RuntimeError("No similarity data for this answer.")

    # Ranks count the answer as #1, so neighbour position p has rank p + 2;
    # the index chooser works in 1-based neighbour positions (rank - 1).
    best_position = None if best_rank_overall is None else best_rank_overall - 1
    idx = _choose_hint_index(n_others, best_position, hint_strength)
    word, sim, rank = ranking.neighbour(idx)

    return {
        "word": word,
        "rank": rank,
        "total": ranking.total,
        "similarity": sim,
        "percentile": compute_percentile(rank, ranking.total),
        "hotness": describe_hotness(rank),
    }
