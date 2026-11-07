from fastapi import APIRouter, Depends

from backend.daily import DailySchedule
from backend.dependencies import get_engine, get_schedule, open_answer
from backend.game import WordGameEngine
from backend.schemas import QuitRequest, QuitResponse
from backend.scoring import calculate_final_score
from backend.utils.scoring import compute_percentile

router = APIRouter()


@router.post("/quit", response_model=QuitResponse)
def quit_endpoint(
    payload: QuitRequest,
    engine: WordGameEngine = Depends(get_engine),
    schedule: DailySchedule = Depends(get_schedule),
) -> QuitResponse:
    answer = open_answer(schedule, payload.puzzle)
    stats = payload.stats
    best_percentile = None
    if stats.best_rank is not None:
        best_percentile = compute_percentile(stats.best_rank, engine.ranking(answer).total)

    score = calculate_final_score(
        False,
        None,
        stats.hint_count,
        stats.similar_count,
        best_percentile,
    )
    return QuitResponse(answer=answer, score=score)
