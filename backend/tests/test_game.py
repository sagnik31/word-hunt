import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import numpy as np
import pytest

from backend.daily import DailySchedule, clue_code, decode, load_clues, schedule_code, seconds_until_next_puzzle
from backend.actions.hint import get_hint, hint_ranks, shares_stem
from backend.game import Ranking, WordGameEngine
from backend.utils.word_forms import KEEP_PLURALS, singular_forms
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
def test_ranking_cache_is_safe_across_threads(engine, monkeypatch):
    # Endpoints run on a thread pool. The race: one thread finds a cached
    # ranking, another evicts it, and the first one's move_to_end raises
    # KeyError. The cache below pauses the first thread right after its hit
    # until the eviction happens, so without the lock this fails every time.
    # With the lock the eviction has to wait, so the pause times out instead.
    cached, other = (str(w) for w in engine.words[:2])
    hit, evicted = threading.Event(), threading.Event()

    class PausingCache(OrderedDict):
        def get(self, key, default=None):
            value = super().get(key, default)
            if key == cached and not hit.is_set():
                hit.set()
                evicted.wait(timeout=0.3)
            return value

        def popitem(self, last=True):
            item = super().popitem(last=last)
            evicted.set()
            return item

    monkeypatch.setattr(engine, "CACHE_SIZE", 1)
    monkeypatch.setattr(engine, "_rankings", PausingCache())
    engine.ranking(cached)
    hit.clear()

    def evict():
        assert hit.wait(timeout=5)
        return engine.ranking(other)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(engine.ranking, cached)
        second = pool.submit(evict)
        assert first.result().answer == cached
        assert second.result().answer == other
    assert list(engine._rankings) == [other]


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


@pytest.mark.parametrize(
    "answer, typed",
    [
        ("larva", "larvae"),  # irregular plurals, guess words of their own
        ("stimulus", "stimuli"),
        ("tongs", "tong"),  # the singular of a plural answer
        ("color", "colour"),  # a British spelling
    ],
)
def test_other_forms_of_the_answer_win(engine, answer, typed):
    result = engine.guess(answer, typed)
    assert result["is_correct"] is True
    assert result["rank"] == 1


def test_a_plural_that_means_something_else_isnt_won_by_its_singular(engine):
    for plural in KEEP_PLURALS:  # spectacles aren't a glass
        assert not set(singular_forms(plural)) & engine.answer_forms(plural)


def test_british_spelling_counts_as_the_american_word(engine):
    plain = engine.guess(ANSWER, "color")
    british = engine.guess(ANSWER, "colour")
    assert british["matched"] == "color"
    assert british["rank"] == plain["rank"]


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


def test_hint_never_reveals_a_plural_of_the_answer():
    # "cats" (rank 2) wins when typed, so it's never revealed, not even as
    # the only word in a shrunken range or by the any-word fallback.
    words = np.array(["cat", "cats", "kitten", "dog", "tail", "mouse", "fur", "sofa"])
    sims = np.array([1.0, 0.95, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4])
    ranking = Ranking("cat", words, sims, 0)
    assert int(ranking.rank_of[1]) == 2
    nothing_ordinary = np.zeros(len(words), dtype=bool)
    assert get_hint(ranking, (2, 2), nothing_ordinary) is None
    for allowed in (nothing_ordinary, np.ones(len(words), dtype=bool)):
        for _ in range(30):
            info = get_hint(ranking, (2, 5), allowed)
            assert info["word"] != "cats" and 3 <= info["rank"] <= 5


@pytest.mark.parametrize(
    "answer, word, shared",
    [
        ("teaspoon", "teaspoonful", True),  # the answer's start
        ("teaspoonful", "spoonful", True),  # one part of a compound
        ("stimulus", "stimulate", True),  # a different ending
        ("stimulus", "impulse", False),
        ("teaspoon", "tea", False),  # too short to count
        ("teaspoon", "teacher", False),
    ],
)
def test_shares_stem(answer, word, shared):
    assert shares_stem(answer, word) is shared


def test_hint_avoids_words_on_the_answers_stem():
    words = np.array(["stimulus", "stimulation", "impulse", "stimuli", "signal", "spark"])
    sims = np.array([1.0, 0.95, 0.9, 0.85, 0.8, 0.7])
    ranking = Ranking("stimulus", words, sims, 0)
    everything = np.ones(len(words), dtype=bool)
    for _ in range(30):
        assert get_hint(ranking, (2, 5), everything)["word"] in {"impulse", "signal"}
    # A rare word beats a giveaway...
    only_stem = np.array([w == "stimulation" for w in words])
    assert get_hint(ranking, (2, 3), only_stem)["word"] == "impulse"
    # ...and the stem word is used only when nothing else is in range.
    assert get_hint(ranking, (2, 2), everything)["word"] == "stimulation"


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
    codes = [schedule_code(w, "secret") for w in ("apple", "piano")]
    assert "apple" not in "".join(codes)
    vocabulary = {"apple", "piano", "tiger"}
    assert decode(codes, "secret", vocabulary) == ["apple", "piano"]
    assert decode(codes, "wrong", vocabulary) == [None, None]


def test_a_clue_code_never_matches_the_schedule():
    # The clues give their word away, so a shared code would give its day away.
    assert schedule_code("apple", "secret") != clue_code("apple", "secret")


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


def test_clues_file_is_keyed_by_clue_codes(tmp_path):
    import json

    path = tmp_path / "clues.json"
    path.write_text(json.dumps({clue_code("apple", "k"): ["a", "b", "c"]}))
    assert load_clues(path, "k", ["apple", "piano", None]) == {"apple": ["a", "b", "c"]}
    assert load_clues(path, "other key", ["apple"]) == {}
    assert load_clues(tmp_path / "missing.json", "k", ["apple"]) == {}


def test_a_hint_range_of_only_answer_forms_widens_to_closer_words():
    words = np.array(["stimulus", "nerve", "stimuli", "far"])
    ranking = Ranking("stimulus", words, np.array([1.0, 0.8, 0.6, 0.1]), 0, {"stimuli"})
    allowed = np.ones(len(words), dtype=bool)
    assert hint_ranks(0, 4) == (3, 3)  # only "stimuli", which wins
    assert get_hint(ranking, (3, 3), allowed)["word"] == "nerve"
