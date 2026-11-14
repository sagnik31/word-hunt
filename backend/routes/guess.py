from typing import Optional

from fastapi import APIRouter, Depends

from backend.daily import DailySchedule
from backend.dependencies import get_engine, get_results, get_schedule, open_answer, save_result
from backend.game import WordGameEngine
from backend.results import Result, ResultStore
from backend.schemas import GuessRequest, GuessResponse
from backend.scoring import solve_score

router = APIRouter()


@router.post("/guess", response_model=GuessResponse)
def make_guess_endpoint(
    payload: GuessRequest,
    engine: WordGameEngine = Depends(get_engine),
    schedule: DailySchedule = Depends(get_schedule),
    results: Optional[ResultStore] = Depends(get_results),
) -> GuessResponse:
    answer = open_answer(schedule, payload.puzzle)
    result = engine.guess(answer, payload.word)

    score = None
    if result.get("is_correct") is True:
        stats = payload.stats
        guesses = stats.guess_count + 1  # the winning guess counts too
        score = solve_score(stats.elapsed_seconds, stats.clue_count, stats.hint_count, guesses)
        save_result(
            results,
            schedule,
            payload.puzzle,
            payload.device_id,
            Result(True, score, guesses, round(stats.elapsed_seconds), stats.clue_count, stats.hint_count),
        )

    return GuessResponse(**result, score=score)
