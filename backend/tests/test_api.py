from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from backend.api import app
from backend.daily import DailySchedule, today_utc

# Yesterday's puzzle (#1) is "piano", today's (#2) is "apple", #3 is tomorrow.
WORDS = ["piano", "apple", "tiger"]
APPLE_CLUES = ["It grows on trees.", "It can be red or green.", "Keeps the doctor away, they say."]


@pytest.fixture(scope="module")
def client():
    # Entering the client runs the app lifespan, which builds the game engine.
    # The real schedule is swapped for a known one, so no key is needed.
    with TestClient(app) as c:
        app.state.schedule = DailySchedule(WORDS, today_utc() - timedelta(days=1))
        app.state.clues = {"apple": APPLE_CLUES}
        yield c


def test_read_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "/today" in response.json()["endpoints"]


def test_health_check(client):
    assert client.get("/health").json() == {"status": "ok", "puzzle_ready": True}


def test_today_names_the_current_puzzle(client):
    data = client.get("/today").json()
    assert data["puzzle"] == 2
    assert data["date"] == today_utc().isoformat()
    assert 0 <= data["seconds_until_next"] <= 24 * 3600


def test_make_guess_invalid(client):
    data = client.post("/guess", json={"puzzle": 2, "word": ""}).json()
    assert data["valid"] is False
    assert data["error"] == "Empty guess."


def test_make_guess_valid(client):
    data = client.post("/guess", json={"puzzle": 2, "word": "dog"}).json()
    assert data["valid"] is True
    assert data["rank"] > 1
    assert data["score"] is None


def test_plural_guess_reports_its_base_word(client):
    data = client.post("/guess", json={"puzzle": 2, "word": "cats"}).json()
    assert data["valid"] is True
    assert data["guess"] == "cats"
    assert data["matched"] == "cat"


def test_each_puzzle_has_its_own_answer(client):
    assert client.post("/guess", json={"puzzle": 1, "word": "piano"}).json()["is_correct"] is True
    assert client.post("/guess", json={"puzzle": 2, "word": "piano"}).json()["is_correct"] is False


def test_winning_guess_is_scored_from_the_players_stats(client):
    # 10 min (14.6), one clue (5), one hint (20), 29 + the winning guess (5)
    stats = {"elapsed_seconds": 600, "guess_count": 29, "clue_count": 1, "hint_count": 1}
    data = client.post("/guess", json={"puzzle": 2, "word": "apple", "stats": stats}).json()
    assert data["is_correct"] is True
    assert data["score"] == 55


@pytest.mark.parametrize("puzzle", [0, 3, 99])
def test_future_and_unknown_puzzles_are_refused(client, puzzle):
    assert client.post("/guess", json={"puzzle": puzzle, "word": "dog"}).status_code == 404
    assert client.post("/quit", json={"puzzle": puzzle}).status_code == 404


def test_hint_requires_post(client):
    assert client.get("/hint").status_code == 405
    response = client.post("/hint", json={"puzzle": 2, "best_rank": 40, "hints_used": 0})
    assert response.status_code == 200
    assert 6 <= response.json()["rank"] <= 10


def test_second_hint_is_closer(client):
    response = client.post("/hint", json={"puzzle": 2, "best_rank": 8, "hints_used": 1})
    assert 2 <= response.json()["rank"] <= 5


@pytest.mark.parametrize("body", [{"best_rank": 2, "hints_used": 0}, {"best_rank": 50, "hints_used": 2}])
def test_no_hint_left_is_a_conflict(client, body):
    assert client.post("/hint", json={"puzzle": 2, **body}).status_code == 409


def test_similar_word_is_gone(client):
    assert client.post("/similar_word", json={"puzzle": 2}).status_code == 404


def test_puzzle_info_gives_the_clue_count(client):
    assert client.get("/puzzle/2").json() == {"puzzle": 2, "clue_total": 3}
    assert client.get("/puzzle/1").json() == {"puzzle": 1, "clue_total": 0}
    assert client.get("/puzzle/3").status_code == 404


def test_quit_reveals_the_answer_and_scores_best_rank(client):
    stats = {"elapsed_seconds": 600, "guess_count": 12, "clue_count": 1, "best_rank": 4}
    data = client.post("/quit", json={"puzzle": 1, "stats": stats}).json()
    assert data["answer"] == "piano"
    assert data["score"] == 14


def test_bad_stats_are_rejected(client):
    response = client.post(
        "/guess", json={"puzzle": 2, "word": "dog", "stats": {"hint_count": -1}}
    )
    assert response.status_code == 422


def test_clues_come_one_at_a_time_vaguest_first(client):
    for used, clue in enumerate(APPLE_CLUES):
        data = client.post("/clue", json={"puzzle": 2, "clues_used": used}).json()
        assert data == {"clue": clue, "number": used + 1, "total": 3}
    assert client.post("/clue", json={"puzzle": 2, "clues_used": 3}).status_code == 409


def test_puzzle_without_clues_says_so(client):
    response = client.post("/clue", json={"puzzle": 1, "clues_used": 0})
    assert response.status_code == 404
    assert response.json()["detail"] == "This puzzle has no clues."


def test_clues_for_future_puzzles_are_refused(client):
    assert client.post("/clue", json={"puzzle": 3, "clues_used": 0}).status_code == 404
