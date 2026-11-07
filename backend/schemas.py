from typing import Optional

from pydantic import BaseModel


class GuessRequest(BaseModel):
    word: str


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
    target_word_loaded: bool


class SimilarWordResponse(BaseModel):
    word: str
    rank: int
    total: int
    similarity: float
    percentile: float
    hotness: str


class HintResponse(BaseModel):
    word: str
    rank: int
    total: int
    similarity: float
    percentile: float
    hotness: str


class QuitResponse(BaseModel):
    answer: str
    score: Optional[int] = None
