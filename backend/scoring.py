"""
Score rules for a finished puzzle.

A solve starts from 100 and loses points for time, help and guesses, but
never drops below SOLVE_FLOOR. A quit earns a small share of what a solve
would have, scaled by how close the player got, and can never reach
SOLVE_FLOOR: a quitter never beats anyone who solved.

All the numbers live in the constants below so they're easy to tune.
"""

from __future__ import annotations

import math
from typing import Optional

# --- Rules ------------------------------------------------------------------

BASE_POINTS = 100
SOLVE_FLOOR = 25  # a solve never scores less

# Time: nothing for TIME_GRACE_MINUTES, then
# TIME_MAX * (1 - e^(-(t - grace) / TIME_SCALE_MINUTES)), t in minutes.
TIME_GRACE_MINUTES = 2.0
TIME_MAX = 30.0
TIME_SCALE_MINUTES = 12.0

# Help: the n-th clue or hint used costs the n-th entry.
CLUE_COSTS = (5, 10, 15)
HINT_COSTS = (20, 25)

# Guesses: GUESS_PENALTY_STEP guesses beyond GUESS_FREE cost 1 point each
# step, up to GUESS_PENALTY_MAX.
GUESS_FREE = 15
GUESS_PENALTY_STEP = 3
GUESS_PENALTY_MAX = 15

# Quit: QUIT_SHARE of the solve score before its floor, times closeness.
# Closeness is 1 at rank 2 and falls to 0 at rank 2 * CLOSENESS_SPAN.
QUIT_SHARE = 0.2
CLOSENESS_SPAN = 500

# The quit rule only works if the best possible quit stays below a solve.
assert QUIT_SHARE * BASE_POINTS < SOLVE_FLOOR


# --- Parts ------------------------------------------------------------------


def time_penalty(seconds: float) -> float:
    """Points lost to the clock, from 0 up to (never quite) TIME_MAX."""
    minutes = max(0.0, seconds) / 60.0
    if minutes <= TIME_GRACE_MINUTES:
        return 0.0
    return TIME_MAX * (1.0 - math.exp(-(minutes - TIME_GRACE_MINUTES) / TIME_SCALE_MINUTES))


def _cost(costs: tuple, used: int) -> int:
    # The game allows no more uses than the table has; older saves from
    # before these rules may report more, and pay for the table only.
    return sum(costs[: max(0, used)])


def clue_cost(clues_used: int) -> int:
    return _cost(CLUE_COSTS, clues_used)


def hint_cost(hints_used: int) -> int:
    return _cost(HINT_COSTS, hints_used)


def help_cost(clues_used: int, hints_used: int) -> int:
    return clue_cost(clues_used) + hint_cost(hints_used)


def guess_penalty(guesses: int) -> int:
    """1 point per GUESS_PENALTY_STEP guesses beyond GUESS_FREE, capped."""
    return min(GUESS_PENALTY_MAX, max(0, guesses - GUESS_FREE) // GUESS_PENALTY_STEP)


def closeness(best_rank: Optional[int]) -> float:
    """How close the best guess got: 1.0 at rank 2, 0.0 at rank 1,000 or worse."""
    if best_rank is None:
        return 0.0
    value = 1.0 - math.log(max(best_rank, 2) / 2) / math.log(CLOSENESS_SPAN)
    return min(1.0, max(0.0, value))


def _round(x: float) -> int:
    # Halves round up (Python's round() would send 14.5 to 14).
    return math.floor(x + 0.5)


def _raw_score(seconds: float, clues_used: int, hints_used: int, guesses: int) -> float:
    return (
        BASE_POINTS
        - time_penalty(seconds)
        - help_cost(clues_used, hints_used)
        - guess_penalty(guesses)
    )


# --- Scores -----------------------------------------------------------------


def solve_score(seconds: float, clues_used: int, hints_used: int, guesses: int) -> int:
    """Score for solving; `guesses` includes the winning one."""
    return max(SOLVE_FLOOR, _round(_raw_score(seconds, clues_used, hints_used, guesses)))


def quit_score(
    seconds: float,
    clues_used: int,
    hints_used: int,
    guesses: int,
    best_rank: Optional[int],
) -> int:
    """Score for quitting: 0 with no guesses, never more than QUIT_SHARE * BASE_POINTS."""
    if guesses <= 0 or best_rank is None:
        return 0
    raw = max(0.0, _raw_score(seconds, clues_used, hints_used, guesses))
    return _round(QUIT_SHARE * raw * closeness(best_rank))
