from typing import Optional

from pydantic import BaseModel


class GuessRequest(BaseModel):
    word: str

class GuessResponse(BaseModel):
    guess: str
    valid: bool
    error: Optional[str] = None
    is_correct: Optional[bool] = None
    rank: Optional[int] = None
    total: Optional[int] = None
    similarity: Optional[float] = None
    percentile: Optional[float] = None
    hotness: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    target_word_loaded: bool

class HintResponse(BaseModel):
    word: str
    rank: int
    total: int
    similarity: float
    percentile: float
    hotness: str

class QuitResponse(BaseModel):
    answer: str
