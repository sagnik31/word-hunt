import itertools

import pytest

from backend import scoring
from backend.scoring import (
    clue_cost,
    closeness,
    guess_penalty,
    hint_cost,
    quit_score,
    solve_score,
    time_penalty,
)


@pytest.mark.parametrize(
    "minutes, penalty",
    [(0, 0.0), (1, 0.0), (2, 0.0), (3, 2.4), (5, 6.6), (10, 14.6), (15, 19.8),
     (20, 23.3), (30, 27.1), (60, 29.8)],
)
def test_time_penalty_table(minutes, penalty):
    assert time_penalty(minutes * 60) == pytest.approx(penalty, abs=0.05)


def test_time_penalty_never_reaches_its_cap():
    assert time_penalty(24 * 3600) <= scoring.TIME_MAX


@pytest.mark.parametrize("used, cost", [(0, 0), (1, 5), (2, 15), (3, 30)])
def test_clue_costs(used, cost):
    assert clue_cost(used) == cost


@pytest.mark.parametrize("used, cost", [(0, 0), (1, 20), (2, 45)])
def test_hint_costs(used, cost):
    assert hint_cost(used) == cost


def test_each_hint_costs_more_than_any_clue():
    assert min(scoring.HINT_COSTS) > max(scoring.CLUE_COSTS)


@pytest.mark.parametrize(
    "guesses, penalty",
    [(0, 0), (15, 0), (17, 0), (18, 1), (20, 1), (30, 5), (45, 10), (60, 15), (500, 15)],
)
def test_guess_penalty(guesses, penalty):
    assert guess_penalty(guesses) == penalty


def test_a_fast_clean_solve_scores_100():
    assert solve_score(90, 0, 0, 10) == 100


def test_solve_subtracts_time_help_and_guesses():
    # 10 min (14.6), clues 1+2 (15), hint 1 (20), 30 guesses (5): 100 - 54.6
    assert solve_score(600, 2, 1, 30) == 45


def test_solve_never_scores_below_the_floor():
    assert solve_score(10 * 3600, 3, 2, 200) == 25


@pytest.mark.parametrize(
    "rank, value", [(1, 1.0), (2, 1.0), (4, 0.89), (10, 0.74), (100, 0.37), (1000, 0.0), (20000, 0.0)]
)
def test_closeness(rank, value):
    assert closeness(rank) == pytest.approx(value, abs=0.005)


def test_quit_example_from_the_rules():
    # Quit at 10 min, best #4, one clue: 0.2 x 80.4 x 0.89 -> 14
    assert quit_score(600, 1, 0, 12, 4) == 14


def test_quit_without_guesses_scores_nothing():
    assert quit_score(600, 0, 0, 0, None) == 0
    assert quit_score(600, 0, 0, 0, 5) == 0


def test_quit_far_away_scores_nothing():
    assert quit_score(60, 0, 0, 5, 1500) == 0


def test_best_possible_quit_is_20():
    assert quit_score(0, 0, 0, 1, 2) == 20


def test_a_quitter_never_beats_a_solver():
    # Over a wide grid, the best quit is below the worst solve.
    seconds = [0, 60, 120, 121, 300, 600, 1800, 3600, 86400]
    clues = range(0, 4)
    hints = range(0, 3)
    guesses = [1, 2, 10, 15, 16, 18, 30, 45, 60, 100, 1000]
    ranks = [1, 2, 3, 4, 5, 10, 50, 100, 999, 1000, 30000]

    worst_solve = min(
        solve_score(s, c, h, g) for s, c, h, g in itertools.product(seconds, clues, hints, guesses)
    )
    best_quit = max(
        quit_score(s, c, h, g, r)
        for s, c, h, g, r in itertools.product(seconds, clues, hints, guesses, ranks)
    )
    assert worst_solve == 25
    assert best_quit == 20
    assert best_quit < worst_solve


def test_quit_and_solve_scores_stay_in_range():
    for s, c, h, g, r in itertools.product(
        [0, 200, 5000], range(4), range(3), [1, 20, 70], [2, 7, 300, 5000]
    ):
        assert 25 <= solve_score(s, c, h, g) <= 100
        assert 0 <= quit_score(s, c, h, g, r) <= 20
