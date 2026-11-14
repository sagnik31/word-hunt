from fastapi import APIRouter, Depends

from backend.daily import DailySchedule
from backend.dependencies import get_engine, get_schedule, open_answer
from backend.game import WordGameEngine
from backend.schemas import GuessRequest, GuessResponse
from backend.scoring import solve_score

router = APIRouter()


@router.post("/guess", response_model=GuessResponse)
def make_guess_endpoint(
    payload: GuessRequest,
    engine: WordGameEngine = Depends(get_engine),
    schedule: DailySchedule = Depends(get_schedule),
) -> GuessResponse:
    answer = open_answer(schedule, payload.puzzle)
    result = engine.guess(answer, payload.word)

    score = None
    if result.get("is_correct") is True:
        stats = payload.stats
        score = solve_score(
            stats.elapsed_seconds,
            stats.clue_count,
            stats.hint_count,
            stats.guess_count + 1,  # the winning guess counts too
        )

    return GuessResponse(**result, score=score)
