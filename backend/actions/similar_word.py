# similar_word.py — Updated smart hint logic

import random
from typing import List, Tuple, Dict, Optional, Literal

from backend.utils.scoring import compute_percentile, describe_hotness

HintStrength = Literal["soft", "strong"]


def _choose_hint_index(
    n_others: int,
    best_rank_overall: Optional[int],
    hint_strength: HintStrength
) -> int:
    """
    Select a rank (index) that is better (lower) than best_rank_overall if possible.
    Soft = modest improvement
    Strong = aggressive improvement
    """
    if best_rank_overall is None or best_rank_overall > 100:
        # Player still far — big window
        if hint_strength == "strong":
            low_rank, high_rank = 1, min(50, n_others)
        else:  # soft
            low_rank, high_rank = 50, min(100, n_others)
            if low_rank > n_others:
                low_rank, high_rank = 1, min(20, n_others)
    else:
        # User already mid-close — give strictly better hint
        best = min(best_rank_overall, n_others)
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
    target_similarity_list: List[Tuple[str, float]],
    target_total: int,
    best_rank_overall: Optional[int],
    hint_strength: HintStrength = "strong",
) -> Dict[str, object]:
    """
    Returns: a dict with:
      word, rank, total, similarity, percentile, hotness
    Ensures hint rank improves the user's best rank when possible.
    """
    if not target_similarity_list:
        raise RuntimeError("No similarity data for this target.")

    n_others = len(target_similarity_list)
    idx = _choose_hint_index(n_others, best_rank_overall, hint_strength)

    word, sim = target_similarity_list[idx]
    rank = idx + 1

    percentile = compute_percentile(rank, target_total)
    hotness = describe_hotness(rank, target_total)

    return {
        "word": word,
        "rank": rank,
        "total": target_total,
        "similarity": sim,
        "percentile": percentile,
        "hotness": hotness,
    }
