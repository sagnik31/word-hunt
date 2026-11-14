from typing import Optional

from fastapi import APIRouter, Depends

from backend.daily import DailySchedule
from backend.dependencies import get_results, get_schedule, open_answer, save_result
from backend.results import Result, ResultStore
from backend.schemas import QuitRequest, QuitResponse
from backend.scoring import quit_score

router = APIRouter()


@router.post("/quit", response_model=QuitResponse)
def quit_endpoint(
    payload: QuitRequest,
    schedule: DailySchedule = Depends(get_schedule),
    results: Optional[ResultStore] = Depends(get_results),
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
    save_result(
        results,
        schedule,
        payload.puzzle,
        payload.device_id,
        Result(False, score, stats.guess_count, round(stats.elapsed_seconds), stats.clue_count, stats.hint_count),
    )
    return QuitResponse(answer=answer, score=score)
