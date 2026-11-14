from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException

from backend.daily import DailySchedule
from backend.dependencies import get_clues, get_engine, get_schedule, open_answer
from backend.game import WordGameEngine
from backend.schemas import ClueRequest, ClueResponse, HintRequest, HintResponse

router = APIRouter()

# The browser decides when the player is stuck enough to unlock the next
# clue or hint, and counts what they've used; the server hands them out.


# Hint: reveal an ordinary word ranked 6-10 (first hint) or 2-5 (second),
# always better than the player's best. 409 when there's nothing to give.
@router.post("/hint", response_model=HintResponse)
def hint_endpoint(
    payload: HintRequest,
    engine: WordGameEngine = Depends(get_engine),
    schedule: DailySchedule = Depends(get_schedule),
) -> HintResponse:
    answer = open_answer(schedule, payload.puzzle)
    info = engine.hint(answer, payload.best_rank, payload.hints_used)
    if info is None:
        raise HTTPException(status_code=409, detail="No hint left to give.")
    return HintResponse(**info)


# Clue: the next of the answer's written clues, vaguest first.
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
