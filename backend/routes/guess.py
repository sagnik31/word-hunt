from typing import Any, Dict

from fastapi import APIRouter, Depends

from backend.dependencies import get_engine
from backend.game import WordGameEngine
from backend.schemas import GuessRequest, GuessResponse
from backend.scoring import calculate_final_score  # <-- NEW IMPORT

router = APIRouter()


@router.post("/guess", response_model=GuessResponse)
def make_guess_endpoint(
    payload: GuessRequest,
    engine: WordGameEngine = Depends(get_engine),
) -> GuessResponse:
    result: Dict[str, Any] = engine.make_guess(payload.word)
    is_correct = result.get("is_correct") is True

    score = None
    if is_correct:
        score = calculate_final_score(
            True,
            engine.start_time,
            engine.hint_count,
            engine.similar_click_count,
            engine.best_percentile,
        )
        # Reset the game for next round
        engine.set_target()

    return GuessResponse(
        **{
            "guess": result.get("guess", ""),
            "valid": bool(result.get("valid", False)),
            "error": result.get("error"),
            "is_correct": result.get("is_correct"),
            "rank": result.get("rank"),
            "total": result.get("total"),
            "similarity": result.get("similarity"),
            "percentile": result.get("percentile"),
            "hotness": result.get("hotness"),
            "score": score,  # <-- ADDED
        }
    )
