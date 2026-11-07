from fastapi import APIRouter, Depends, HTTPException

from backend.daily import DailySchedule, seconds_until_next_puzzle, today_utc
from backend.dependencies import get_schedule
from backend.schemas import TodayResponse

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
