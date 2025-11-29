from typing import Any, Dict
from fastapi import APIRouter, Depends
from backend.schemas import GuessRequest, GuessResponse
from backend.game import WordGameEngine
from backend.dependencies import get_engine

router = APIRouter()

@router.post("/guess", response_model=GuessResponse)
def make_guess_endpoint(
    payload: GuessRequest,
    engine: WordGameEngine = Depends(get_engine),
) -> GuessResponse:
    result: Dict[str, Any] = engine.make_guess(payload.word)
    return GuessResponse(**{
        "guess": result.get("guess", ""),
        "valid": bool(result.get("valid", False)),
        "error": result.get("error"),
        "is_correct": result.get("is_correct"),
        "rank": result.get("rank"),
        "total": result.get("total"),
        "similarity": result.get("similarity"),
        "percentile": result.get("percentile"),
        "hotness": result.get("hotness"),
    })
