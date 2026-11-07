from fastapi import APIRouter, Depends

from backend.daily import DailySchedule
from backend.dependencies import get_engine, get_schedule, open_answer
from backend.game import WordGameEngine
from backend.schemas import HelpRequest, SuggestionResponse

router = APIRouter()

# Hint and Similar Word work the same way: each reveals a word ranked better
# than the player's best so far, and gets stronger after 3 uses. The browser
# counts the uses of each one separately and sends that count.


def _suggest(payload: HelpRequest, engine: WordGameEngine, schedule: DailySchedule) -> SuggestionResponse:
    answer = open_answer(schedule, payload.puzzle)
    return SuggestionResponse(**engine.suggest(answer, payload.best_rank, payload.times_used))


@router.post("/hint", response_model=SuggestionResponse)
def hint_endpoint(
    payload: HelpRequest,
    engine: WordGameEngine = Depends(get_engine),
    schedule: DailySchedule = Depends(get_schedule),
) -> SuggestionResponse:
    return _suggest(payload, engine, schedule)


@router.post("/similar_word", response_model=SuggestionResponse)
def similar_word_endpoint(
    payload: HelpRequest,
    engine: WordGameEngine = Depends(get_engine),
    schedule: DailySchedule = Depends(get_schedule),
) -> SuggestionResponse:
    return _suggest(payload, engine, schedule)
