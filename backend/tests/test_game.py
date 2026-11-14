from datetime import date

import pytest

from backend.daily import DailySchedule, decode, seconds_until_next_puzzle, word_code
from backend.actions.hint import hint_ranks
from backend.game import WordGameEngine
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


# --- Hints ------------------------------------------------------------------


@pytest.mark.parametrize(
    "hints_used, best, ranks",
    [
        (0, None, (6, 10)),
        (0, 500, (6, 10)),
        (0, 11, (6, 10)),
        (0, 8, (6, 7)),  # a best inside the range shrinks it
        (0, 6, (5, 5)),
        (0, 3, (2, 2)),
        (1, None, (2, 5)),
        (1, 40, (2, 5)),
        (1, 4, (2, 3)),
        (0, 2, None),  # only the answer is closer
        (1, 2, None),
        (2, None, None),  # both hints used
    ],
)
def test_hint_ranks(hints_used, best, ranks):
    assert hint_ranks(hints_used, best) == ranks


@pytest.mark.parametrize("hints_used, low, high", [(0, 6, 10), (1, 2, 5)])
def test_hint_reveals_an_ordinary_word_in_its_range(engine, ranking, hints_used, low, high):
    for _ in range(30):
        info = engine.hint(ANSWER, None, hints_used)
        assert low <= info["rank"] <= high
        i = engine.word_index[info["word"]]
        assert ranking.rank_of[i] == info["rank"]
        assert engine.hint_ok[i]
        assert info["total"] == ranking.total


def test_hint_always_beats_the_best_rank(engine):
    for best in (9, 7, 6, 4, 3):
        for used in (0, 1):
            for _ in range(10):
                assert engine.hint(ANSWER, best, used)["rank"] < best


def test_no_hint_when_only_the_answer_is_closer(engine):
    assert engine.hint(ANSWER, 2, 0) is None
    assert engine.hint(ANSWER, None, 2) is None


def test_hint_words_leave_out_rare_and_inflected_words(engine):
    ok = {str(w) for w, flag in zip(engine.words, engine.hint_ok) if flag}
    assert {"cat", "sofa", "skid", "fishing"} <= ok
    assert not {"skidded", "marshy"} & ok


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


# --- Temperature labels ------------------------------------------------------


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


def test_clues_file_is_keyed_by_word_codes(tmp_path):
    import json

    from backend.daily import load_clues, word_code

    path = tmp_path / "clues.json"
    path.write_text(json.dumps({word_code("apple", "k"): ["a", "b", "c"]}))
    assert load_clues(path, "k", ["apple", "piano", None]) == {"apple": ["a", "b", "c"]}
    assert load_clues(path, "other key", ["apple"]) == {}
    assert load_clues(tmp_path / "missing.json", "k", ["apple"]) == {}
