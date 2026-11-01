import pytest

from backend.game import WordGameEngine
from backend.scoring import calculate_final_score

TARGET = "aardvark"
# Appears twice in common_nouns.txt, so its similarity row once contained itself.
REPEATED_TARGET = "america"


@pytest.fixture
def engine():
    return WordGameEngine(target_word=TARGET)


def _guess_at_rank(engine, rank):
    # The target is rank 1, so neighbour index i is rank i + 2.
    word = engine.target_similarity_list[rank - 2][0]
    result = engine.make_guess(word)
    assert result["rank"] == rank
    return word


@pytest.mark.parametrize("method", ["get_hint", "get_similar_word"])
def test_suggestion_is_a_ranked_neighbour(engine, method):
    info = getattr(engine, method)()
    assert info["word"] != TARGET
    assert engine.target_similarity_list[info["rank"] - 2][0] == info["word"]
    assert info["total"] == engine.target_total


@pytest.mark.parametrize("method", ["get_hint", "get_similar_word"])
def test_suggestion_beats_best_rank(engine, method):
    _guess_at_rank(engine, 50)
    for _ in range(20):
        best = engine.best_rank_overall
        info = getattr(engine, method)()
        # Once the closest neighbour (rank 2) is found there's nothing better.
        assert info["rank"] < best or best == 2
        assert engine.best_rank_overall == min(best, info["rank"])


def test_closest_neighbour_is_not_the_answer(engine):
    result = engine.make_guess(engine.target_similarity_list[0][0])
    assert result["is_correct"] is False
    assert result["rank"] == 2
    assert result["hotness"] != "Correct"
    assert result["percentile"] < 100.0


def test_correct_guess_is_rank_one(engine):
    result = engine.make_guess(TARGET)
    assert result["is_correct"] is True
    assert result["rank"] == 1
    assert result["hotness"] == "Correct"


def test_ranking_excludes_target_and_repeats():
    e = WordGameEngine(target_word=REPEATED_TARGET)
    words = [w for w, _ in e.target_similarity_list]
    assert REPEATED_TARGET not in words
    assert len(words) == len(set(words))
    assert e.target_total == len(words) + 1


def test_hint_never_reveals_the_answer():
    e = WordGameEngine(target_word=REPEATED_TARGET)
    _guess_at_rank(e, 3)
    for _ in range(50):
        assert e.get_hint()["word"] != REPEATED_TARGET


def test_next_target_is_never_the_same_word(engine):
    for _ in range(20):
        previous = engine.get_target()
        assert engine.set_target() != previous


def test_clock_starts_on_first_action(engine):
    assert engine.start_time is None
    engine.make_guess("")
    assert engine.start_time is not None


def test_counters_are_tracked_separately(engine):
    engine.get_hint()
    engine.get_hint()
    engine.get_similar_word()
    assert engine.hint_count == 2
    assert engine.similar_click_count == 1


def test_each_help_feature_has_its_own_strength(engine):
    assert engine._determine_hint_strength(engine.hint_count) == "soft"
    for _ in range(3):
        engine.get_hint()
    assert engine._determine_hint_strength(engine.hint_count) == "strong"
    # Hints used so far don't make Similar Word stronger, and vice versa.
    assert engine._determine_hint_strength(engine.similar_click_count) == "soft"


def test_quitting_after_help_scores_less_than_quitting_without():
    no_help = calculate_final_score(False, None, 0, 0, 99.0)
    one_hint = calculate_final_score(False, None, 1, 0, 99.0)
    assert no_help == 50
    assert one_hint == 40


def test_quitting_never_beats_a_quick_solve():
    best_quit = calculate_final_score(False, None, 0, 0, 100.0)
    quick_solve = calculate_final_score(True, 0.0, 0, 0, None, now=5.0)
    assert best_quit < quick_solve == 100
