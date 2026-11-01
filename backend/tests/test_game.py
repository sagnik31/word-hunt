import pytest

from backend.game import WordGameEngine

TARGET = "aardvark"


@pytest.fixture
def engine():
    return WordGameEngine(target_word=TARGET)


def _guess_at_rank(engine, rank):
    word = engine.target_similarity_list[rank - 1][0]
    result = engine.make_guess(word)
    assert result["rank"] == rank
    return word


@pytest.mark.parametrize("method", ["get_hint", "get_similar_word"])
def test_suggestion_is_a_ranked_neighbour(engine, method):
    info = getattr(engine, method)()
    assert info["word"] != TARGET
    assert engine.target_similarity_list[info["rank"] - 1][0] == info["word"]
    assert info["total"] == engine.target_total


@pytest.mark.parametrize("method", ["get_hint", "get_similar_word"])
def test_suggestion_beats_best_rank(engine, method):
    _guess_at_rank(engine, 50)
    for _ in range(20):
        best = engine.best_rank_overall
        info = getattr(engine, method)()
        assert info["rank"] < best or best == 1
        assert engine.best_rank_overall == min(best, info["rank"])


def test_counters_are_tracked_separately(engine):
    engine.get_hint()
    engine.get_hint()
    engine.get_similar_word()
    assert engine.hint_count == 2
    assert engine.similar_click_count == 1


def test_hint_strength_follows_hint_count(engine):
    assert engine._determine_hint_strength() == "soft"
    for _ in range(3):
        engine.get_hint()
    assert engine._determine_hint_strength() == "strong"
    # Similar Word clicks don't change hint strength.
    engine.hint_count = 0
    for _ in range(5):
        engine.get_similar_word()
    assert engine._determine_hint_strength() == "soft"
