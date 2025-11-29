from typing import Optional
import random

from backend.schemas import HintStrength

def _choose_hint_index(
    n_others: int,
    best_rank_overall: Optional[int],
    hint_strength: HintStrength,
) -> int:
    """
    Decide which rank (0-based index) to use for the hint.

    Assumes:
      - target_similarity_list is sorted by descending similarity
      - rank = index + 1
      - best_rank_overall is in the same rank space (1 = best)

    Strategy:
      - If best_rank_overall is None or very bad (> 100), we use fixed bands.
      - Otherwise, we choose a rank strictly better than best_rank_overall.
      - Soft vs strong controls how aggressive the improvement is.
    """
    # No good info yet or user is still far (wild guesses)
    if best_rank_overall is None or best_rank_overall > 100:
        # Use fixed bands in terms of rank.
        # For strong hints: give something in 1–50 (or up to n_others).
        # For soft hints: 50–100, if possible.
        if hint_strength == "strong":
            low_rank = 1
            high_rank = min(50, n_others)
        else:  # "soft"
            low_rank = 50
            high_rank = 100
            if low_rank > n_others:  # too small vocab, fall back
                low_rank = 1
                high_rank = min(20, n_others)
            else:
                high_rank = min(high_rank, n_others)
    else:
        # We already have a reasonably good rank (<= 100).
        # Always try to suggest a STRICTLY better rank.
        best = min(best_rank_overall, n_others)  # safety clamp

        if best <= 1:
            # Already at the best possible rank; nothing to improve.
            # Just suggest somewhere in the top band.
            low_rank = 1
            high_rank = min(5, n_others)
        else:
            if hint_strength == "strong":
                # Aggressive improvement: anywhere from 1 up to (best - 1)
                low_rank = 1
                high_rank = best - 1
            else:
                # Soft improvement: a window just above the best rank.
                # Example: if best=80, window might be [40, 79].
                improvement_window = max(5, best // 2)
                low_rank = max(1, best - improvement_window)
                high_rank = best - 1

    # Clamp to valid range [1, n_others]
    low_rank = max(1, min(low_rank, n_others))
    high_rank = max(1, min(high_rank, n_others))

    # If the window has collapsed (low > high), fall back to top 20
    if low_rank > high_rank:
        low_rank = 1
        high_rank = min(20, n_others)

    # Convert to 0-based index
    return random.randint(low_rank - 1, high_rank - 1)
