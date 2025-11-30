# backend/scoring.py
"""
Final scoring logic for the Word Hot-Cold game.

This module is intentionally kept separate from the core game engine so that
scoring rules can be tweaked or swapped out without touching gameplay logic.

Current rules (V1):
- Base: 100 points for a correct guess.
- Time penalty:
    * 0–10s   : 0 penalty
    * 10–30s  : mild linear increase
    * 30–120s : faster (non-linear) increase
    * 120s+   : slow linear tail, capped overall
- Help penalty:
    * Each hint:          -10 points
    * Each similar word:  -10 points
- Quit:
    * Score = round(100 * best_percentile_reached)
    * If no valid guesses (percentile <= 0 or None) → 0 points.
- Final score is never negative.
"""

from __future__ import annotations

import time
from typing import Optional


def base_points(is_correct: bool) -> int:
    """
    Base points just for solving the puzzle.
    """
    return 100 if is_correct else 0


def time_penalty(seconds: float) -> int:
    """
    Time-based penalty with three phases:

    1. 0–10 seconds  : no penalty (players can think a bit)
    2. 10–30 seconds : mild linear penalty, up to ~10 points
    3. 30–120 seconds: faster non-linear increase (steep region)
    4. 120+ seconds  : slow tail that increases gently, capped overall

    The constants are intentionally conservative so that scores don't
    instantly drop to zero for taking more time; they can be tuned later
    after some playtesting.
    """
    if seconds <= 10:
        return 0

    # 10–30s: mild linear increase up to ~10 points
    if seconds <= 30:
        # Example: 20s -> ~5, 30s -> ~10
        return int((seconds - 10) / 2)

    # 30–120s: steeper non-linear (quadratic) increase
    if seconds <= 120:
        extra = seconds - 30.0  # 0–90
        t = extra / 90.0  # normalized 0–1
        # Penalty ranges roughly from 10 to 40 over this window
        return 10 + int(30 * (t ** 2))

    # Beyond 120s: slow linear tail, capped
    extra = seconds - 120.0
    # Start around 40, then +1 every 30s, capped at 60
    penalty = 40 + int(extra / 30.0)
    return min(penalty, 60)


def help_penalty(hint_count: int, similar_count: int) -> int:
    """
    Penalty for consuming help.

    For V1 we treat:
      - each hint, and
      - each similar word request
    the same: -10 points each.

    Keeping them separate as inputs makes it easy to change their relative
    weight in the future (e.g., -8 for hints, -5 for similar words, etc.).
    """
    return 10 * hint_count + 10 * similar_count


def quit_partial_score(best_percentile: Optional[float]) -> int:
    """
    Partial score when the user quits.

    We use the best percentile achieved so far (0–100) and simply map:
      score = round(best_percentile)

    i.e., if best_percentile is 72.3, the player gets 72 points.

    If no meaningful progress was made (None or <= 0), return 0.
    """
    if best_percentile is None or best_percentile <= 0.0:
        return 0

    # best_percentile is already 0–100
    return int(round(best_percentile))


def calculate_final_score(
    is_correct: bool,
    start_time: float,
    hint_count: int,
    similar_count: int,
    best_percentile: Optional[float],
    now: Optional[float] = None,
) -> int:
    """
    Main entrypoint for computing the final score for a round.

    Parameters
    ----------
    is_correct : bool
        Whether the round ended with a correct guess (True) or a quit (False).
    start_time : float
        UNIX timestamp (time.time()) recorded when the round began.
    hint_count : int
        Number of hints used in this round.
    similar_count : int
        Number of similar-word requests used in this round.
    best_percentile : Optional[float]
        Best percentile achieved across guesses/hints (0–100).
        Used only when is_correct == False (quit case).
    now : Optional[float]
        Optional override for the "current time" (useful for tests).
        If None, time.time() will be used.

    Returns
    -------
    int
        Final score for the round, clamped to a minimum of 0.
    """
    # Quit case: use percentile-based partial score
    if not is_correct:
        score = quit_partial_score(best_percentile)
        return max(score, 0)

    # Correct case: compute time + help penalties
    current_time = time.time() if now is None else now
    elapsed = max(0.0, current_time - start_time)

    score = base_points(True)
    score -= time_penalty(elapsed)
    score -= help_penalty(hint_count, similar_count)

    return max(score, 0)
