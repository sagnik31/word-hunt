from typing import Optional

from pydantic import BaseModel, Field


class PlayerStats(BaseModel):
    """The player's progress on a puzzle, kept in their browser."""

    elapsed_seconds: float = Field(0.0, ge=0)  # since the clock started
    guess_count: int = Field(0, ge=0)  # valid guesses before this request
    clue_count: int = Field(0, ge=0)  # clues used
    hint_count: int = Field(0, ge=0)  # hints used
    best_rank: Optional[int] = Field(None, ge=1)


class GuessRequest(BaseModel):
    puzzle: int
    word: str
    stats: PlayerStats = Field(default_factory=PlayerStats)


class HintRequest(BaseModel):
    puzzle: int
    best_rank: Optional[int] = Field(None, ge=1)
    hints_used: int = Field(0, ge=0)  # hints already shown on this puzzle


class ClueRequest(BaseModel):
    puzzle: int
    clues_used: int = Field(0, ge=0)  # clues already shown on this puzzle


class QuitRequest(BaseModel):
    puzzle: int
    stats: PlayerStats = Field(default_factory=PlayerStats)


class TodayResponse(BaseModel):
    puzzle: int  # today's puzzle number; every puzzle from 1 up to it is playable
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
