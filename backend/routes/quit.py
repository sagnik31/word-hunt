from fastapi import APIRouter, Depends

from backend.daily import DailySchedule
from backend.dependencies import get_schedule, open_answer
from backend.schemas import QuitRequest, QuitResponse
from backend.scoring import quit_score

router = APIRouter()


@router.post("/quit", response_model=QuitResponse)
def quit_endpoint(
    payload: QuitRequest,
    schedule: DailySchedule = Depends(get_schedule),
) -> QuitResponse:
    answer = open_answer(schedule, payload.puzzle)
    stats = payload.stats
    score = quit_score(
        stats.elapsed_seconds,
        stats.clue_count,
        stats.hint_count,
        stats.guess_count,
        stats.best_rank,
    )
    return QuitResponse(answer=answer, score=score)
