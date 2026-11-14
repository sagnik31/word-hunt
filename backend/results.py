"""
Results: one row per device per puzzle, for "you beat X% of today's players".

Only plays finished on the puzzle's own UTC day are stored. The device ID is
a random string the browser keeps in localStorage: no accounts, nothing
personal. The database is Postgres in production (Neon, via DATABASE_URL)
and SQLite in tests; both run the same SQL.

Nothing here connects at startup. The first query opens the connection, so
the server starts even when the database is paused or unreachable. Neon's
free plan pauses after about 5 idle minutes and drops open connections, so a
failed query reconnects and retries once; the first request after a pause
takes about a second longer.
"""

import math
import re
import sqlite3
import threading
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

# Below this many players on a day, show "Only N players so far" instead of
# a percentage.
MIN_PLAYERS = 10

# Bars of the guess chart: how many guesses solvers took. None = no limit.
GUESS_BUCKETS: Tuple[Tuple[int, Optional[int]], ...] = (
    (1, 5),
    (6, 10),
    (11, 15),
    (16, 20),
    (21, 30),
    (31, 50),
    (51, 100),
    (101, None),
)

# What the browser may send as its device ID (it sends a UUID).
DEVICE_ID_PATTERN = r"^[A-Za-z0-9-]{8,64}$"
_DEVICE_ID_RE = re.compile(DEVICE_ID_PATTERN)

SCHEMA = """
CREATE TABLE IF NOT EXISTS results (
    puzzle     INTEGER   NOT NULL,
    device_id  TEXT      NOT NULL,
    solved     BOOLEAN   NOT NULL,
    score      INTEGER   NOT NULL,
    guesses    INTEGER   NOT NULL,
    seconds    INTEGER   NOT NULL,
    clues      INTEGER   NOT NULL,
    hints      INTEGER   NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (puzzle, device_id)
)
"""


def valid_device_id(device_id: Optional[str]) -> bool:
    return bool(device_id) and _DEVICE_ID_RE.match(device_id) is not None


@dataclass(frozen=True)
class Result:
    solved: bool
    score: int
    guesses: int  # valid guesses, the winning one included
    seconds: int  # since Play was pressed
    clues: int
    hints: int


@dataclass(frozen=True)
class Row:
    device_id: str
    solved: bool
    score: int
    guesses: int


class ResultStore:
    """One shared connection, opened on first use and reopened once on error."""

    placeholder = "?"

    def __init__(self):
        self._conn = None
        self._lock = threading.Lock()

    def _connect(self):  # pragma: no cover - each backend overrides it
        raise NotImplementedError

    def _run(self, sql: str, params: Sequence = (), fetch: bool = False):
        sql = sql.replace("?", self.placeholder)
        with self._lock:
            for attempt in (1, 2):
                try:
                    if self._conn is None:
                        self._conn = self._connect()
                        self._conn.execute(SCHEMA)
                    cur = self._conn.execute(sql, params)
                    return cur.fetchall() if fetch else cur.rowcount
                except Exception:
                    # A dropped connection (Neon paused) or a broken one:
                    # start again with a fresh connection, once.
                    self._drop_connection()
                    if attempt == 2:
                        raise

    def _drop_connection(self):
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def close(self):
        with self._lock:
            self._drop_connection()

    def record(self, puzzle: int, device_id: str, result: Result) -> bool:
        """Store a result; a device's first result for a puzzle is the one kept."""
        count = self._run(
            "INSERT INTO results (puzzle, device_id, solved, score, guesses, seconds, clues, hints) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (puzzle, device_id) DO NOTHING",
            (
                puzzle,
                device_id,
                result.solved,
                result.score,
                result.guesses,
                result.seconds,
                result.clues,
                result.hints,
            ),
        )
        return count == 1

    def day(self, puzzle: int) -> List[Row]:
        rows = self._run(
            "SELECT device_id, solved, score, guesses FROM results WHERE puzzle = ?",
            (puzzle,),
            fetch=True,
        )
        return [Row(d, bool(s), int(sc), int(g)) for d, s, sc, g in rows]


class SQLiteResultStore(ResultStore):
    """For tests and local runs. ":memory:" lives as long as the store."""

    def __init__(self, path: str = ":memory:"):
        super().__init__()
        self.path = path

    def _connect(self):
        return sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)


class PostgresResultStore(ResultStore):
    placeholder = "%s"

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    def _connect(self):
        import psycopg

        # prepare_threshold=None: no server-side prepared statements, which
        # a pooled (PgBouncer) connection string may not support.
        return psycopg.connect(self.url, autocommit=True, connect_timeout=10, prepare_threshold=None)


def open_store(url: Optional[str]) -> Optional[ResultStore]:
    """The store DATABASE_URL names, or None (results off) when unset or unknown."""
    url = (url or "").strip()
    if not url:
        return None
    if url.startswith(("postgres://", "postgresql://")):
        return PostgresResultStore(url)
    if url.startswith("sqlite:///"):
        return SQLiteResultStore(url[len("sqlite:///"):] or ":memory:")
    return None


def _round_half_up(x: float) -> int:
    return math.floor(x + 0.5)


def summarize(
    rows: List[Row],
    device_id: Optional[str] = None,
    score: Optional[int] = None,
) -> Dict:
    """How a player compares with a puzzle's on-the-day players.

    If this device's own result is stored, it's the one compared and it's
    left out of the field it's compared against. Otherwise (an archive play,
    or a play that wasn't stored) `score` is compared against everyone.
    Ties count as half.
    """
    mine = next((r for r in rows if device_id and r.device_id == device_id), None)
    others = [r for r in rows if r is not mine]
    if mine is not None:
        score = mine.score

    players = len(rows)
    solvers = [r for r in rows if r.solved]

    beat = None
    if score is not None and players >= MIN_PLAYERS and others:
        below = sum(r.score < score for r in others)
        ties = sum(r.score == score for r in others)
        beat = _round_half_up(100 * (below + ties / 2) / len(others))

    buckets = []
    for low, high in GUESS_BUCKETS:
        count = sum(r.guesses >= low and (high is None or r.guesses <= high) for r in solvers)
        buckets.append({"low": low, "high": high, "count": count})

    return {
        "players": players,
        "solvers": len(solvers),
        "solve_rate": _round_half_up(100 * len(solvers) / players) if players else None,
        "beat_percent": beat,
        "counted": mine is not None,
        "min_players": MIN_PLAYERS,
        "buckets": buckets,
    }
