from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException

from backend.daily import DailySchedule
from backend.dependencies import get_clues, get_engine, get_schedule, open_answer
from backend.game import WordGameEngine
from backend.schemas import ClueRequest, ClueResponse, HelpRequest, SuggestionResponse

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


# Clue: the next of the answer's written clues, vaguest first. The browser
# decides when the player is stuck enough to unlock one.
@router.post("/clue", response_model=ClueResponse)
def clue_endpoint(
    payload: ClueRequest,
    schedule: DailySchedule = Depends(get_schedule),
    clues: Dict[str, List[str]] = Depends(get_clues),
) -> ClueResponse:
    answer = open_answer(schedule, payload.puzzle)
    answer_clues = clues.get(answer)
    if not answer_clues:
        raise HTTPException(status_code=404, detail="This puzzle has no clues.")
    if payload.clues_used >= len(answer_clues):
        raise HTTPException(status_code=409, detail="No clues left.")
    return ClueResponse(
        clue=answer_clues[payload.clues_used],
        number=payload.clues_used + 1,
        total=len(answer_clues),
    )
