import traceback
from typing import Dict, List, Optional

from fastapi import HTTPException, Request

from backend.daily import DailySchedule
from backend.game import WordGameEngine
from backend.results import Result, ResultStore, valid_device_id


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


def get_results(request: Request) -> Optional[ResultStore]:
    """The results store; None when no DATABASE_URL is set."""
    return getattr(request.app.state, "results", None)


def save_result(
    store: Optional[ResultStore],
    schedule: DailySchedule,
    puzzle: int,
    device_id: Optional[str],
    result: Result,
) -> None:
    """Store a finished play, if it was finished on the puzzle's own day.

    Archive plays aren't stored. A database error is logged, not raised: the
    player's guess or quit still goes through.
    """
    if store is None or not valid_device_id(device_id) or puzzle != schedule.current():
        return
    try:
        store.record(puzzle, device_id, result)
    except Exception as e:
        print(f"[results] Could not store a result: {e}")
        traceback.print_exc()
