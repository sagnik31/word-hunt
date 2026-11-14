from backend.results import (
    MIN_PLAYERS,
    PostgresResultStore,
    Result,
    Row,
    SQLiteResultStore,
    open_store,
    summarize,
    valid_device_id,
)


def result(solved=True, score=80, guesses=12):
    return Result(solved=solved, score=score, guesses=guesses, seconds=300, clues=1, hints=0)


def test_store_keeps_the_first_result_per_device():
    store = SQLiteResultStore()
    assert store.record(5, "device-aaaa", result(score=80)) is True
    assert store.record(5, "device-aaaa", result(score=99)) is False
    assert store.record(6, "device-aaaa", result(score=50)) is True
    assert store.day(5) == [Row("device-aaaa", True, 80, 12)]
    assert store.day(7) == []


def test_store_reconnects_after_a_dropped_connection(tmp_path):
    store = SQLiteResultStore(str(tmp_path / "results.db"))
    store.record(1, "device-aaaa", result())
    store._conn.close()  # as when Neon pauses and drops the connection
    assert store.record(1, "device-bbbb", result(solved=False, score=10)) is True
    assert len(store.day(1)) == 2


def test_open_store_picks_the_backend():
    assert open_store(None) is None
    assert open_store("  ") is None
    assert open_store("mysql://x") is None
    assert isinstance(open_store("sqlite:///:memory:"), SQLiteResultStore)
    pg = open_store("postgresql://user:pw@host/db?sslmode=require")
    assert isinstance(pg, PostgresResultStore)
    assert pg._conn is None  # nothing connects until the first query


def test_device_ids():
    assert valid_device_id("3f2b6c1e-8d4a-4f7e-9b1c-2a5d6e7f8a9b")
    assert not valid_device_id(None)
    assert not valid_device_id("short")
    assert not valid_device_id("has space in it")


def rows(scores, solved=True, guesses=10):
    return [Row(f"device-{i:04d}", solved, s, guesses) for i, s in enumerate(scores)]


def test_few_players_give_no_percentage():
    summary = summarize(rows([50] * (MIN_PLAYERS - 1)), score=60)
    assert summary["players"] == MIN_PLAYERS - 1
    assert summary["beat_percent"] is None


def test_beat_percent_counts_ties_as_half():
    # Archive play: compared against all ten on-the-day players.
    summary = summarize(rows([10, 20, 30, 40, 50, 60, 60, 70, 80, 90]), score=60)
    assert summary["counted"] is False
    assert summary["beat_percent"] == 60  # 5 below + 2 ties / 2 = 6 of 10


def test_own_result_is_compared_and_left_out_of_the_field():
    field = rows([10] * 10)
    mine = Row("me-device-1", True, 90, 8)
    summary = summarize(field + [mine], device_id="me-device-1", score=5)
    assert summary["counted"] is True
    assert summary["players"] == 11
    assert summary["beat_percent"] == 100  # the stored 90 wins over the sent 5


def test_solve_rate_and_guess_chart():
    field = rows([80, 70, 60], guesses=4) + rows([40], guesses=17) + rows([5, 0], solved=False, guesses=30)
    summary = summarize(field)
    assert summary["solvers"] == 4
    assert summary["solve_rate"] == 67
    counts = {(b["low"], b["high"]): b["count"] for b in summary["buckets"]}
    assert counts[(1, 5)] == 3
    assert counts[(16, 20)] == 1
    assert counts[(21, 30)] == 0  # quitters aren't in the chart
    assert summary["buckets"][-1]["high"] is None


def test_empty_day():
    summary = summarize([], score=50)
    assert summary["players"] == 0
    assert summary["solve_rate"] is None
    assert summary["beat_percent"] is None
