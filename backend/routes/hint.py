from fastapi import APIRouter, Depends
from backend.schemas import HintResponse
from backend.game import WordGameEngine
from backend.dependencies import get_engine

router = APIRouter()

@router.get("/hint", response_model=HintResponse)
def hint_endpoint(
    engine: WordGameEngine = Depends(get_engine),
) -> HintResponse:
    """
    Suggest a 'hot' word: randomly selected from top-N most similar words
    to the current target.
    """
    info = engine.get_hint(top_n=10)
    return HintResponse(**info)
