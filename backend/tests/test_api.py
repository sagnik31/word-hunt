from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from backend.api import app
from backend.daily import DailySchedule, today_utc

# Yesterday's puzzle (#1) is "piano", today's (#2) is "apple", #3 is tomorrow.
WORDS = ["piano", "apple", "tiger"]


@pytest.fixture(scope="module")
def client():
    # Entering the client runs the app lifespan, which builds the game engine.
    # The real schedule is swapped for a known one, so no key is needed.
    with TestClient(app) as c:
        app.state.schedule = DailySchedule(WORDS, today_utc() - timedelta(days=1))
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
    stats = {"elapsed_seconds": 5, "hint_count": 1, "similar_count": 1}
    data = client.post("/guess", json={"puzzle": 2, "word": "apple", "stats": stats}).json()
    assert data["is_correct"] is True
    assert data["score"] == 80  # 100 minus 10 per help, no time penalty yet


@pytest.mark.parametrize("puzzle", [0, 3, 99])
def test_future_and_unknown_puzzles_are_refused(client, puzzle):
    assert client.post("/guess", json={"puzzle": puzzle, "word": "dog"}).status_code == 404
    assert client.post("/quit", json={"puzzle": puzzle}).status_code == 404


@pytest.mark.parametrize("path", ["/hint", "/similar_word"])
def test_help_endpoints_require_post(client, path):
    assert client.get(path).status_code == 405
    response = client.post(path, json={"puzzle": 2, "best_rank": 40, "times_used": 0})
    assert response.status_code == 200
    assert 2 <= response.json()["rank"] < 40


def test_quit_reveals_the_answer_and_scores_best_rank(client):
    data = client.post("/quit", json={"puzzle": 1, "stats": {"best_rank": 2}}).json()
    assert data["answer"] == "piano"
    assert data["score"] == 50


def test_bad_stats_are_rejected(client):
    response = client.post(
        "/guess", json={"puzzle": 2, "word": "dog", "stats": {"hint_count": -1}}
    )
    assert response.status_code == 422
