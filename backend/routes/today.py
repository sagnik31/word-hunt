from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException

from backend.daily import DailySchedule, seconds_until_next_puzzle, today_utc
from backend.dependencies import get_clues, get_schedule, open_answer
from backend.schemas import PuzzleResponse, TodayResponse

router = APIRouter()


@router.get("/today", response_model=TodayResponse)
def today_endpoint(schedule: DailySchedule = Depends(get_schedule)) -> TodayResponse:
    today = today_utc()
    number = schedule.number_on(today)
    if not schedule.is_open(number, today):
        raise HTTPException(status_code=503, detail="No puzzle is scheduled for today.")
    return TodayResponse(
        puzzle=number,
        date=today.isoformat(),
        launch_date=schedule.launch.isoformat(),
        seconds_until_next=seconds_until_next_puzzle(),
    )


# What the browser needs to know about a puzzle before play: how many clues
# it has, so the help ladder can go straight to hints when there are none.
@router.get("/puzzle/{number}", response_model=PuzzleResponse)
def puzzle_endpoint(
    number: int,
    schedule: DailySchedule = Depends(get_schedule),
    clues: Dict[str, List[str]] = Depends(get_clues),
) -> PuzzleResponse:
    answer = open_answer(schedule, number)
    return PuzzleResponse(puzzle=number, clue_total=len(clues.get(answer) or []))
