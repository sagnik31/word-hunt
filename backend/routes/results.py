from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.daily import DailySchedule
from backend.dependencies import get_results, get_schedule, open_answer
from backend.results import ResultStore, summarize
from backend.schemas import ResultsResponse

router = APIRouter()


# How a finished play compares with the puzzle's on-the-day players. The
# device's own stored result is used when there is one; otherwise `score` (an
# archive play, which isn't stored) is compared against that day's players.
@router.get("/results/{number}", response_model=ResultsResponse)
def results_endpoint(
    number: int,
    device_id: Optional[str] = Query(None, max_length=100),
    score: Optional[int] = Query(None, ge=0, le=100),
    schedule: DailySchedule = Depends(get_schedule),
    store: Optional[ResultStore] = Depends(get_results),
) -> ResultsResponse:
    open_answer(schedule, number)  # 404 for future puzzles
    if store is None:
        raise HTTPException(status_code=503, detail="Results aren't available.")
    try:
        rows = store.day(number)
    except Exception as e:
        print(f"[results] Could not read results: {e}")
        raise HTTPException(status_code=503, detail="Results aren't available right now.")
    return ResultsResponse(puzzle=number, **summarize(rows, device_id, score))
