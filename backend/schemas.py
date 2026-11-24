from typing import Annotated, List, Optional

from pydantic import BaseModel, BeforeValidator, Field

from backend.results import valid_device_id


# Generous limits on what a browser can send, so a hand-made request (an
# endless clock, a count too big for the results table) gets a 422, not a 500.
MAX_SECONDS = 10 * 366 * 24 * 3600  # ten years
MAX_COUNT = 100_000
MAX_WORD_LENGTH = 100


class PlayerStats(BaseModel):
    """The player's progress on a puzzle, kept in their browser."""

    elapsed_seconds: float = Field(0.0, ge=0, le=MAX_SECONDS, allow_inf_nan=False)  # since the clock started
    guess_count: int = Field(0, ge=0, le=MAX_COUNT)  # different words guessed before this request
    clue_count: int = Field(0, ge=0, le=MAX_COUNT)  # clues used
    hint_count: int = Field(0, ge=0, le=MAX_COUNT)  # hints used
    best_rank: Optional[int] = Field(None, ge=1, le=MAX_COUNT * 10)


# The browser's random device ID, so results count once per device. Anything
# that doesn't look like one is ignored rather than refused.
DeviceId = Annotated[Optional[str], BeforeValidator(lambda v: v if valid_device_id(v) else None)]


class GuessRequest(BaseModel):
    puzzle: int
    word: str = Field(max_length=MAX_WORD_LENGTH)
    stats: PlayerStats = Field(default_factory=PlayerStats)
    device_id: DeviceId = None


class HintRequest(BaseModel):
    puzzle: int
    best_rank: Optional[int] = Field(None, ge=1, le=MAX_COUNT * 10)
    hints_used: int = Field(0, ge=0, le=MAX_COUNT)  # hints already shown on this puzzle


class ClueRequest(BaseModel):
    puzzle: int
    clues_used: int = Field(0, ge=0, le=MAX_COUNT)  # clues already shown on this puzzle


class QuitRequest(BaseModel):
    puzzle: int
    stats: PlayerStats = Field(default_factory=PlayerStats)
    device_id: DeviceId = None


class TodayResponse(BaseModel):
    puzzle: Optional[int] = None  # today's puzzle number; None once the schedule has run out
    latest: int  # the newest released puzzle; every puzzle from 1 up to it is playable
    date: str  # today's UTC date, YYYY-MM-DD
    launch_date: str  # date of puzzle #1
    seconds_until_next: int


class GuessResponse(BaseModel):
    guess: str
    # The base word the guess counted as ("cats" -> "cat"), if different.
    matched: Optional[str] = None
    valid: bool
    error: Optional[str] = None
    is_correct: Optional[bool] = None
    rank: Optional[int] = None
    total: Optional[int] = None
    similarity: Optional[float] = None
    percentile: Optional[float] = None
    hotness: Optional[str] = None
    score: Optional[int] = None


class HealthResponse(BaseModel):
    status: str
    puzzle_ready: bool
    results: bool  # a results database is configured (not checked: Neon may be asleep)


class PuzzleResponse(BaseModel):
    puzzle: int
    clue_total: int  # written clues this puzzle has; 0 when none


class HintResponse(BaseModel):
    word: str
    rank: int
    total: int
    similarity: float
    percentile: float
    hotness: str


class ClueResponse(BaseModel):
    clue: str
    number: int  # 1 is the vaguest
    total: int


class QuitResponse(BaseModel):
    answer: str
    score: Optional[int] = None


class GuessBucket(BaseModel):
    low: int
    high: Optional[int] = None  # None: no upper limit
    count: int  # solvers whose guess count falls in low..high


class ResultsResponse(BaseModel):
    """How a player compares with the puzzle's on-the-day players."""

    puzzle: int
    players: int  # results stored for the puzzle's own day
    solvers: int
    solve_rate: Optional[int] = None  # percent; None with no players
    beat_percent: Optional[int] = None  # None below min_players, or with no score
    counted: bool  # this device's result is one of the players
    min_players: int
    buckets: List[GuessBucket]
