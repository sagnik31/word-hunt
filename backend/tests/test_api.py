from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from backend.api import app
from backend.daily import DailySchedule, schedule_code, today_utc
from backend.results import MIN_PLAYERS, Result, SQLiteResultStore

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
        app.state.results = SQLiteResultStore()  # in memory; no real database
        yield c


@pytest.fixture
def fresh_results(client):
    app.state.results = SQLiteResultStore()
    yield app.state.results


def test_read_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "/today" in response.json()["endpoints"]
    assert response.json()["message"] == app.title == "Word Hunt API"


def test_cors_allows_the_site_without_credentials(client):
    # The game uses no cookies, so browsers aren't told to send them.
    origin = "https://sagnik31.github.io"
    response = client.options(
        "/guess", headers={"Origin": origin, "Access-Control-Request-Method": "POST"}
    )
    assert response.headers["access-control-allow-origin"] == origin
    assert "access-control-allow-credentials" not in response.headers
    blocked = client.options(
        "/guess", headers={"Origin": "https://example.com", "Access-Control-Request-Method": "POST"}
    )
    assert "access-control-allow-origin" not in blocked.headers


def test_health_check(client):
    assert client.get("/health").json() == {"status": "ok", "puzzle_ready": True, "results": True}


def test_health_is_503_when_degraded(client):
    # A failed startup must fail Render's health check, so a broken deploy
    # never replaces a working one.
    schedule = app.state.schedule
    app.state.schedule = None
    try:
        response = client.get("/health")
        assert response.status_code == 503
        assert response.json()["status"] == "degraded"
    finally:
        app.state.schedule = schedule


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


# --- Results ----------------------------------------------------------------

ME = "11111111-2222-4333-8444-555555555555"
WIN_STATS = {"elapsed_seconds": 90, "guess_count": 7, "clue_count": 0, "hint_count": 0}


def test_a_solve_on_its_day_is_stored_once(client, fresh_results):
    body = {"puzzle": 2, "word": "apple", "stats": WIN_STATS, "device_id": ME}
    assert client.post("/guess", json=body).json()["score"] == 100
    # A second solve from the same device (another tab, say) doesn't count.
    # It shows the first score, which is the one compared with other players.
    again = client.post("/guess", json={**body, "stats": {**WIN_STATS, "elapsed_seconds": 3000}})
    assert again.json()["score"] == 100
    # A quit afterwards doesn't get the solve's score.
    late = client.post("/quit", json={"puzzle": 2, "stats": {"guess_count": 3}, "device_id": ME})
    assert late.json()["score"] <= 20
    [row] = fresh_results.day(2)
    assert (row.solved, row.score, row.guesses) == (True, 100, 8)


def test_a_quit_on_its_day_is_stored(client, fresh_results):
    stats = {"elapsed_seconds": 600, "guess_count": 12, "clue_count": 1, "best_rank": 4}
    client.post("/quit", json={"puzzle": 2, "stats": stats, "device_id": ME})
    row = fresh_results.day(2)[0]
    assert (row.solved, row.score, row.guesses) == (False, 14, 12)


def test_archive_plays_and_bad_device_ids_are_not_stored(client, fresh_results):
    client.post("/guess", json={"puzzle": 1, "word": "piano", "device_id": ME})
    client.post("/quit", json={"puzzle": 1, "device_id": ME})
    response = client.post("/guess", json={"puzzle": 2, "word": "apple", "device_id": "no good!"})
    assert response.status_code == 200
    client.post("/guess", json={"puzzle": 2, "word": "apple"})  # no device ID at all
    assert fresh_results.day(1) == [] and fresh_results.day(2) == []


def test_results_compare_against_the_days_players(client, fresh_results):
    for i in range(MIN_PLAYERS):
        fresh_results.record(2, f"other-device-{i:02d}", Result(True, 50 + i, 10, 300, 0, 0))
    body = {"puzzle": 2, "word": "apple", "stats": WIN_STATS, "device_id": ME}
    client.post("/guess", json=body)
    data = client.get(f"/results/2?device_id={ME}").json()
    assert data["counted"] is True
    assert data["players"] == MIN_PLAYERS + 1
    assert data["beat_percent"] == 100
    assert data["solve_rate"] == 100
    assert {"low": 6, "high": 10, "count": MIN_PLAYERS + 1} in data["buckets"]


def test_archive_results_use_the_sent_score(client, fresh_results):
    for i in range(MIN_PLAYERS):
        fresh_results.record(1, f"other-device-{i:02d}", Result(True, 40 + 10 * (i % 4), 10, 300, 0, 0))
    data = client.get(f"/results/1?device_id={ME}&score=50").json()
    assert data["counted"] is False
    # Scores 40, 50, 60, 70 (x3, x3, x2, x2): 3 below, 3 ties -> 4.5 of 10.
    assert data["beat_percent"] == 45


def test_few_players_and_future_puzzles(client, fresh_results):
    data = client.get("/results/2?score=80").json()
    assert data["players"] == 0 and data["beat_percent"] is None
    assert client.get("/results/3").status_code == 404


def test_results_off_without_a_database(client):
    store = app.state.results
    app.state.results = None
    try:
        assert client.get("/health").json()["results"] is False
        assert client.get("/results/2").status_code == 503
        body = {"puzzle": 2, "word": "apple", "device_id": ME}
        assert client.post("/guess", json=body).json()["is_correct"] is True
        assert client.post("/quit", json={"puzzle": 2, "device_id": ME}).status_code == 200
    finally:
        app.state.results = store


class BrokenStore:
    def record(self, *args):
        raise ConnectionError("database unreachable")

    def day(self, puzzle):
        raise ConnectionError("database unreachable")


def test_a_database_error_never_breaks_play(client):
    store = app.state.results
    app.state.results = BrokenStore()
    try:
        body = {"puzzle": 2, "word": "apple", "device_id": ME}
        assert client.post("/guess", json=body).json()["is_correct"] is True
        assert client.get("/results/2").status_code == 503
    finally:
        app.state.results = store


@pytest.mark.parametrize("seconds", ["Infinity", "NaN", "1e300"])
@pytest.mark.parametrize("route, word", [("/quit", None), ("/guess", "apple")])
def test_an_impossible_clock_is_refused(client, route, word, seconds):
    # Hand-made JSON; a browser never sends these. They used to give a 500.
    body = '{"puzzle": 2, %s"stats": {"elapsed_seconds": %s, "best_rank": 4}}' % (
        f'"word": "{word}", ' if word else "",
        seconds,
    )
    response = client.post(route, content=body, headers={"Content-Type": "application/json"})
    assert response.status_code == 422


def test_counts_too_big_for_the_results_table_are_refused(client):
    stats = {"guess_count": 10**12}
    assert client.post("/quit", json={"puzzle": 2, "stats": stats}).status_code == 422


def test_a_very_long_word_is_refused(client):
    assert client.post("/guess", json={"puzzle": 2, "word": "a" * 1000}).status_code == 422


@pytest.mark.parametrize("device_id", [None, "", "short", "a" * 101, 5, ["x"], "has a space in it"])
def test_a_bad_device_id_never_blocks_play(client, fresh_results, device_id):
    body = {"puzzle": 2, "word": "apple", "stats": {}, "device_id": device_id}
    assert client.post("/guess", json=body).json()["is_correct"] is True
    assert client.post("/quit", json={"puzzle": 2, "stats": {}, "device_id": device_id}).status_code == 200
    assert client.get("/results/2", params={"device_id": str(device_id)}).status_code == 200
    assert fresh_results.day(2) == []


def test_the_archive_stays_open_when_the_schedule_runs_out(client, monkeypatch):
    # Three puzzles, launched a week ago.
    monkeypatch.setattr(app.state, "schedule", DailySchedule(WORDS, today_utc() - timedelta(days=7)))
    data = client.get("/today").json()
    assert data["puzzle"] is None
    assert data["latest"] == len(WORDS)
    assert client.get("/puzzle/3").status_code == 200


def test_today_is_503_before_launch(client, monkeypatch):
    monkeypatch.setattr(app.state, "schedule", DailySchedule(WORDS, today_utc() + timedelta(days=1)))
    assert client.get("/today").status_code == 503


@pytest.mark.parametrize("bad_lines, status", [(0, 200), (1, 503), (2, 503)])
def test_health_fails_when_the_schedule_doesnt_decode(tmp_path, monkeypatch, bad_lines, status):
    codes = [schedule_code("piano", "some-test-key")] * (2 - bad_lines) + ["0" * 20] * bad_lines
    path = tmp_path / "schedule.txt"
    path.write_text("\n".join(codes) + "\n", encoding="utf-8")
    monkeypatch.setattr("backend.api.SCHEDULE_PATH", path)
    monkeypatch.setattr("backend.api.CLUES_PATH", tmp_path / "none.json")
    monkeypatch.setattr("backend.api.schedule_key", lambda: "some-test-key")
    monkeypatch.setattr("backend.api.database_url", lambda: None)
    # The lifespan runs on the shared app: put its state back afterwards.
    state = dict(app.state._state)
    try:
        with TestClient(app) as c:
            assert c.get("/health").status_code == status
    finally:
        app.state._state.update(state)
