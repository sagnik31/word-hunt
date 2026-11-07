import pytest

from backend.game import WordGameEngine
from backend.scoring import calculate_final_score

TARGET = "apple"


@pytest.fixture(scope="module")
def shared_engine():
    # Loading the embeddings is the slow part, so do it once per module.
    return WordGameEngine(target_word=TARGET)


@pytest.fixture
def engine(shared_engine):
    shared_engine.set_target(TARGET)  # fresh round for each test
    return shared_engine


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


def test_ranking_covers_every_other_guess_word(engine):
    words = [w for w, _ in engine.target_similarity_list]
    assert TARGET not in words
    assert len(words) == len(set(words))
    assert set(words) | {TARGET} == engine.vocab_set
    assert engine.target_total == len(words) + 1


def test_ranking_is_sorted_by_similarity(engine):
    sims = [s for _, s in engine.target_similarity_list]
    assert sims == sorted(sims, reverse=True)
    assert sims[0] < 1.0
    # Related words rank far better than unrelated ones.
    pos = engine.target_pos_map
    assert pos["fruit"] < 100 < pos["tax"]


def test_targets_come_from_the_target_list(engine):
    targets = set(engine.targets)
    for _ in range(20):
        assert engine.set_target() in targets


def test_hint_never_reveals_the_answer(engine):
    _guess_at_rank(engine, 3)
    for _ in range(50):
        assert engine.get_hint()["word"] != TARGET


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


def test_plural_of_the_answer_wins(engine):
    result = engine.make_guess(TARGET + "s")
    assert result["is_correct"] is True
    assert result["guess"] == TARGET + "s"
    assert result["matched"] == TARGET


def test_inflected_guess_counts_as_its_base_word(engine):
    plain = engine.make_guess("cat")
    plural = engine.make_guess("Cats")
    assert plural["valid"] is True
    assert plural["matched"] == "cat"
    assert plural["rank"] == plain["rank"]
    assert plain["matched"] is None


def test_unknown_word_is_still_rejected(engine):
    result = engine.make_guess("xqzzt")
    assert result["valid"] is False
    assert result["matched"] is None
