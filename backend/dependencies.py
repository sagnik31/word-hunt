from typing import Dict, List

from fastapi import HTTPException, Request

from backend.daily import DailySchedule
from backend.game import WordGameEngine


def get_engine(request: Request) -> WordGameEngine:
    engine = getattr(request.app.state, "engine", None)
    if engine is None:
        raise HTTPException(status_code=503, detail="Game engine not initialized.")
    return engine


def get_schedule(request: Request) -> DailySchedule:
    schedule = getattr(request.app.state, "schedule", None)
    if schedule is None:
        raise HTTPException(status_code=503, detail="Daily schedule not loaded.")
    return schedule


def get_clues(request: Request) -> Dict[str, List[str]]:
    """Clues by answer word; empty when the clues file is missing."""
    return getattr(request.app.state, "clues", None) or {}


def open_answer(schedule: DailySchedule, puzzle: int) -> str:
    """The answer to a released puzzle; 404 for future or unknown puzzles."""
    if not schedule.is_open(puzzle):
        raise HTTPException(status_code=404, detail=f"Puzzle #{puzzle} isn't available.")
    return schedule.answer(puzzle)
