from datetime import date

import pytest

from backend.daily import DailySchedule, decode, seconds_until_next_puzzle, word_code
from backend.game import WordGameEngine
from backend.scoring import calculate_final_score
from backend.utils.scoring import describe_hotness

ANSWER = "apple"


@pytest.fixture(scope="module")
def engine():
    # Loading the embeddings is the slow part, so do it once per module.
    return WordGameEngine()


@pytest.fixture(scope="module")
def ranking(engine):
    return engine.ranking(ANSWER)


def _word_at_rank(ranking, rank):
    word, _, r = ranking.neighbour(rank - 2)
    assert r == rank
    return word


# --- Ranking ----------------------------------------------------------------


def test_ranking_covers_every_other_guess_word(engine, ranking):
    words = [str(engine.words[i]) for i in ranking.order]
    assert ANSWER not in words
    assert len(words) == len(set(words))
    assert set(words) | {ANSWER} == engine.vocab_set
    assert ranking.total == len(words) + 1


def test_ranking_is_sorted_by_similarity(engine, ranking):
    sims = ranking.sims[ranking.order]
    assert all(sims[:-1] >= sims[1:])
    assert sims[0] < 1.0
    # Related words rank far better than unrelated ones.
    rank = ranking.rank_of
    assert rank[engine.word_index["fruit"]] < 100 < rank[engine.word_index["tax"]]


def test_rankings_are_cached(engine):
    assert engine.ranking(ANSWER) is engine.ranking(ANSWER)


# --- Guesses ----------------------------------------------------------------


def test_closest_neighbour_is_not_the_answer(engine, ranking):
    result = engine.guess(ANSWER, _word_at_rank(ranking, 2))
    assert result["is_correct"] is False
    assert result["rank"] == 2
    assert result["hotness"] != "Correct"
    assert result["percentile"] < 100.0


def test_correct_guess_is_rank_one(engine):
    result = engine.guess(ANSWER, ANSWER)
    assert result["is_correct"] is True
    assert result["rank"] == 1
    assert result["hotness"] == "Correct"


def test_plural_of_the_answer_wins(engine):
    result = engine.guess(ANSWER, ANSWER + "s")
    assert result["is_correct"] is True
    assert result["guess"] == ANSWER + "s"
    assert result["matched"] == ANSWER


def test_inflected_guess_counts_as_its_base_word(engine):
    plain = engine.guess(ANSWER, "cat")
    plural = engine.guess(ANSWER, "Cats")
    assert plural["valid"] is True
    assert plural["matched"] == "cat"
    assert plural["rank"] == plain["rank"]
    assert plain["matched"] is None


@pytest.mark.parametrize(
    "word, error",
    [("", "Empty guess."), ("xqzzt", "Word is not in the allowed vocabulary.")],
)
def test_invalid_guesses_are_rejected(engine, word, error):
    result = engine.guess(ANSWER, word)
    assert result["valid"] is False
    assert result["error"] == error
    assert result["matched"] is None


# --- Hint and Similar Word --------------------------------------------------


def test_suggestion_is_a_ranked_neighbour(engine, ranking):
    info = engine.suggest(ANSWER, None, 0)
    assert info["word"] != ANSWER
    assert ranking.rank_of[engine.word_index[info["word"]]] == info["rank"]
    assert info["total"] == ranking.total


@pytest.mark.parametrize("times_used", [0, 5])
def test_suggestion_beats_best_rank(engine, times_used):
    best = 50
    for _ in range(20):
        info = engine.suggest(ANSWER, best, times_used)
        # Once the closest neighbour (rank 2) is found there's nothing better.
        assert info["rank"] < best or best == 2
        best = min(best, info["rank"])


def test_hint_never_reveals_the_answer(engine):
    for best in (None, 3, 2):
        for _ in range(30):
            assert engine.suggest(ANSWER, best, 5)["word"] != ANSWER


def test_help_gets_stronger_after_three_uses(engine):
    assert [engine.hint_strength(n) for n in range(5)] == ["soft"] * 3 + ["strong"] * 2


# --- Daily schedule ---------------------------------------------------------

LAUNCH = date(2026, 1, 1)


def test_puzzle_numbers_follow_the_utc_date():
    schedule = DailySchedule(["apple", "piano", "tiger"], LAUNCH)
    assert schedule.number_on(LAUNCH) == 1
    assert schedule.number_on(date(2026, 1, 3)) == 3
    assert schedule.date_of(3) == date(2026, 1, 3)
    assert schedule.answer(2) == "piano"


def test_only_released_puzzles_are_open():
    schedule = DailySchedule(["apple", "piano", "tiger", None], LAUNCH)
    today = date(2026, 1, 2)  # puzzle #2
    assert [schedule.is_open(n, today) for n in (0, 1, 2, 3)] == [False, True, True, False]
    later = date(2026, 3, 1)
    assert not schedule.is_open(4, later)  # a code that didn't decode
    assert not schedule.is_open(5, later)  # past the end of the schedule


def test_schedule_codes_hide_words_and_need_the_key():
    codes = [word_code(w, "secret") for w in ("apple", "piano")]
    assert "apple" not in "".join(codes)
    vocabulary = {"apple", "piano", "tiger"}
    assert decode(codes, "secret", vocabulary) == ["apple", "piano"]
    assert decode(codes, "wrong", vocabulary) == [None, None]


def test_next_puzzle_countdown_is_within_a_day():
    assert 0 <= seconds_until_next_puzzle() <= 24 * 3600


# --- Scoring ----------------------------------------------------------------


def test_quitting_after_help_scores_less_than_quitting_without():
    no_help = calculate_final_score(False, None, 0, 0, 99.0)
    one_hint = calculate_final_score(False, None, 1, 0, 99.0)
    assert no_help == 50
    assert one_hint == 40


def test_quitting_never_beats_a_quick_solve():
    best_quit = calculate_final_score(False, None, 0, 0, 100.0)
    quick_solve = calculate_final_score(True, 0.0, 0, 0, None, now=5.0)
    assert best_quit < quick_solve == 100


@pytest.mark.parametrize(
    "rank, label",
    [
        (1, "Correct"),
        (2, "Boiling"),
        (10, "Boiling"),
        (11, "Very hot"),
        (30, "Very hot"),
        (100, "Hot"),
        (300, "Warm"),
        (600, "Cool"),
        (1000, "Cold"),
        (1001, "Freezing"),
        (30000, "Freezing"),
    ],
)
def test_hotness_bands_are_rank_based(rank, label):
    assert describe_hotness(rank) == label
